FROM python:3.11-slim

WORKDIR /app

RUN pip install websockets httpx

RUN curl -fsSL https://raw.githubusercontent.com/cp4r3z/p4r3z_pi/refs/heads/main/monitor.py -o monitor.py

#COPY monitor.py .

CMD ["python", "-u", "monitor.py"]
