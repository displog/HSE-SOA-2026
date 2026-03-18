FROM python:3.12-slim

WORKDIR /app

COPY booking-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY proto /app/proto
COPY booking-service /app/booking-service

# Generate gRPC client code
RUN pip install grpcio-tools && python -m grpc_tools.protoc \
  -I /app/proto \
  --python_out=/app/booking-service/generated \
  --grpc_python_out=/app/booking-service/generated \
  /app/proto/flight_service.proto

ENV PYTHONPATH=/app/booking-service:/app/booking-service/generated

WORKDIR /app/booking-service

RUN sed -i 's/\r$//' /app/booking-service/entrypoint.sh && chmod +x /app/booking-service/entrypoint.sh

ENTRYPOINT ["/app/booking-service/entrypoint.sh"]
