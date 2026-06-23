FROM python:3.12-slim

WORKDIR /app

COPY historian_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY historian_service/app ./historian_service/app
COPY proto ./proto

EXPOSE 50051
EXPOSE 9101

CMD ["python", "-m", "historian_service.app.grpc_server"]
