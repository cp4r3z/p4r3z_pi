FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN pip install websockets httpx
RUN curl -fsSL https://raw.githubusercontent.com/cp4r3z/p4r3z_pi/refs/heads/main/monitor.py -o monitor.py

CMD ["python", "-u", "monitor.py"]
