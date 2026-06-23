FROM python:3.12-slim

WORKDIR /app

COPY alarm_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alarm_service ./alarm_service
COPY proto ./proto

EXPOSE 50052
EXPOSE 9102

CMD ["python", "-m", "alarm_service.app.grpc_server"]
