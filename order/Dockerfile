FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN mkdir -p /data

ENV ORDER_DB_PATH=/data/orders.db

EXPOSE 5002

CMD ["python", "app.py"]