import logging
import os

import grpc
from concurrent import futures

from app.auth_interceptor import AuthInterceptor
from app.flight_servicer import FlightServicer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import generated after PYTHONPATH is set
from generated import flight_service_pb2_grpc


def serve():
    port = os.environ.get("FLIGHT_GRPC_PORT", "50051")
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=[AuthInterceptor()],
    )
    flight_service_pb2_grpc.add_FlightServiceServicer_to_server(FlightServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logger.info("Flight Service listening on port %s", port)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
