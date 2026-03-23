import asyncio
import json
import time
import httpx
import websockets
from datetime import timedelta

# --- Configuration ---
ZWAVEJS_WS_URL = "ws://zwave-js-ui:3000"   # WebSocket URL for Z-Wave JS UI
#ZWAVEJS_WS_URL = "ws://pihole.local:3000"   # WebSocket URL for Z-Wave JS UI (debugging on local network)
POWER_NODE_ID = 2                           # Change to your power meter's node ID
POWER_VALUE_ID = "49-0-Power"        # Change to match your meter's value ID
KEY_W_CONSUMED = 'Electric_W_Consumed'
POWER_THRESHOLD_W = 5.0                     # Watts above this = device is ON
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


async def send_notification(title, message, priority="default"):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                NTFY_URL,
                content=message,
                headers={
                    "Title": title,
                    "Priority": priority,
                    "Tags": "droplet", #"potable_water",
                },
            )
        print(f"[ntfy] Sent: {title} — {message}")
    except Exception as e:
        print(f"[ntfy] Failed to send notification: {e}")


async def handle_value_update_power(data):
    global start_time, is_running

    key = data.get("args", {}).get("propertyKeyName")
    current_value = data.get("args", {}).get("newValue")

    if key != KEY_W_CONSUMED:
        return

    print(f"[monitor] Node {POWER_NODE_ID} power reading: {current_value}W")

    if current_value >= POWER_THRESHOLD_W and not is_running:
        # Device just turned ON
        is_running = True
        start_time = time.time()
        print(f"[monitor] {APPLIANCE_NAME} started")
        await send_notification(
            f"{APPLIANCE_NAME} Started",
            f"{APPLIANCE_NAME} turned on ({current_value}W)",
            priority="default"
        )

    elif current_value < POWER_THRESHOLD_W and is_running:
        # Device just turned OFF
        is_running = False
        duration = time.time() - start_time
        start_time = None
        duration_str = format_duration(duration)
        print(f"[monitor] {APPLIANCE_NAME} stopped after {duration_str}")
        await send_notification(
            f"{APPLIANCE_NAME} Finished",
            f"{APPLIANCE_NAME} ran for {duration_str}",
            priority="high"
        )


async def handle_value_update_garage(data):
    # TODO: implement garage door sensor handling
    current_value = data.get("args", {}).get("newValue")
    print(f"[monitor] Garage door sensor update: {current_value}")


async def handle_value_update(data):
    try:
        node_id = data.get("nodeId")

        if node_id == POWER_NODE_ID:
            await handle_value_update_power(data)
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