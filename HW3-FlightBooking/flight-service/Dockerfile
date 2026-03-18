FROM python:3.12-slim

WORKDIR /app

COPY flight-service/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY proto /app/proto
COPY flight-service /app/flight-service

# Generate gRPC code
RUN python -m grpc_tools.protoc \
  -I /app/proto \
  --python_out=/app/flight-service/generated \
  --grpc_python_out=/app/flight-service/generated \
  /app/proto/flight_service.proto

ENV PYTHONPATH=/app/flight-service:/app/flight-service/generated

WORKDIR /app/flight-service

RUN sed -i 's/\r$//' /app/flight-service/entrypoint.sh && chmod +x /app/flight-service/entrypoint.sh

ENTRYPOINT ["/app/flight-service/entrypoint.sh"]
