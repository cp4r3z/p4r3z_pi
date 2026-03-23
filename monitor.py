import asyncio
import json
import time
import httpx
import websockets
from datetime import timedelta, datetime

# --- Configuration ---
ZWAVEJS_WS_URL = "ws://zwave-js-ui:3000"   # WebSocket URL for Z-Wave JS UI
#ZWAVEJS_WS_URL = "ws://pihole.local:3000"   # WebSocket URL for Z-Wave JS UI (debugging on local network)
SUMP_PUMP_NODE_ID = 2                       # Z-Wave node ID for sump pump power meter
SUMP_PUMP_VALUE_ID = "49-0-Power"           # Value ID for sump pump power meter
KEY_W_CONSUMED = 'Electric_W_Consumed'
SUMP_PUMP_THRESHOLD_W = 5.0                 # Watts above this = sump pump is ON
NTFY_URL = "https://ntfy.sh/p4r3z_pi"  # Change topic to match your ntfy topic
APPLIANCE_NAME = "Sump Pump"               # Friendly name for notifications
GARAGE_NODE_ID = 6                          # Z-Wave node ID for garage door sensor
GARAGE_VALUE_ID = "48-0-Any"               # Value ID for garage door sensor
# ---------------------

start_time = None
is_running = False


def format_duration(seconds):
    td = timedelta(seconds=int(seconds))
    hours, remainder = divmod(td.seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


async def send_notification(title, message, priority="default", tags="bell"):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                NTFY_URL,
                content=message,
                headers={
                    "Title": title,
                    "Priority": priority,
                    "Tags": tags,
                },
            )
        print(f"[ntfy] Sent: {title} — {message}")
    except Exception as e:
        print(f"[ntfy] Failed to send notification: {e}")


async def handle_value_update_sump_pump(data):
    global start_time, is_running

    key = data.get("args", {}).get("propertyKeyName")
    current_value = data.get("args", {}).get("newValue")

    if key != KEY_W_CONSUMED:
        return

    print(f"[monitor] Node {SUMP_PUMP_NODE_ID} power reading: {current_value}W")

    if current_value >= SUMP_PUMP_THRESHOLD_W and not is_running:
        # Device just turned ON
        is_running = True
        start_time = time.time()
        print(f"[monitor] {APPLIANCE_NAME} started")
        await send_notification(
            f"{APPLIANCE_NAME} Started",
            f"{APPLIANCE_NAME} turned on ({current_value}W)",
            priority="default",
            tags="droplet"
        )

    elif current_value < SUMP_PUMP_THRESHOLD_W and is_running:
        # Device just turned OFF
        is_running = False
        duration = time.time() - start_time
        start_time = None
        duration_str = format_duration(duration)
        print(f"[monitor] {APPLIANCE_NAME} stopped after {duration_str}")
        await send_notification(
            f"{APPLIANCE_NAME} Finished",
            f"{APPLIANCE_NAME} ran for {duration_str}",
            priority="high",
            tags="droplet"
        )


async def handle_value_update_garage(data):
    current_value = data.get("args", {}).get("newValue")
    print(f"[monitor] Garage door sensor update: {current_value}")

    if current_value is True:
        now = datetime.now()
        print(f"[monitor] Garage door opened at {now.strftime('%H:%M:%S')}")
        if now.hour >= 21:
            await send_notification(
                "Garage Door Opened",
                f"Garage door opened at {now.strftime('%I:%M %p')}",
                priority="high",
                tags="oncoming_automobile"
            )


async def handle_value_update(data):
    try:
        node_id = data.get("nodeId")

        if node_id == SUMP_PUMP_NODE_ID:
            await handle_value_update_sump_pump(data)
        elif node_id == GARAGE_NODE_ID:
            await handle_value_update_garage(data)

    except Exception as e:
        print(f"[monitor] Error handling value update: {e}")


async def connect():
    while True:
        try:
            print(f"[monitor] Connecting to Z-Wave JS UI at {ZWAVEJS_WS_URL}...")
            async with websockets.connect(f"{ZWAVEJS_WS_URL}") as ws:
                print("[monitor] Connected!")

                # Send the init message required by Z-Wave JS UI
                await ws.send(json.dumps({
                    "messageId": "init",
                    "command": "initialize",
                    "schemaVersion": 44
                }))

                # Wait for init response
                await ws.recv()

                # Subscribe to node value updates
                await ws.send(json.dumps({
                    "messageId": "start-listening",
                    "command": "start_listening",
                }))

                async for raw_message in ws:
                    try:
                        msg = json.loads(raw_message)
                        event = msg.get("event", {})
                        #print(f"[debug] {json.dumps(msg)[:200]}")
                        
                        if event.get("source") == "node" and event.get("event") == "value updated":
                            await handle_value_update(event)

                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            print(f"[monitor] Connection error: {e}. Retrying in 10 seconds...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(connect())