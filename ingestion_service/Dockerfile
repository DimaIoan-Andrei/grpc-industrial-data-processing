FROM python:3.12-slim

WORKDIR /app

COPY ingestion_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ingestion_service/app ./app
COPY proto ./proto

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
