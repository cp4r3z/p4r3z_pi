FROM python:3.11-slim

WORKDIR /app

RUN pip install websockets httpx

COPY monitor.py .

CMD ["python", "-u", "monitor.py"]
