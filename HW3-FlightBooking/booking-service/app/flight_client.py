import logging
import os
import time
from enum import Enum
from typing import Callable, TypeVar

import grpc
import jwt
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerError(Exception):
    """Raised when circuit is OPEN."""
    pass


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 15.0,
        success_threshold: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None

    def _should_trip(self) -> bool:
        if self.state == CircuitState.OPEN:
            if self.last_failure_time and (time.monotonic() - self.last_failure_time) >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info("CircuitBreaker: OPEN -> HALF_OPEN")
                return False
            return True
        return False

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("CircuitBreaker: HALF_OPEN -> CLOSED")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        self.last_failure_time = time.monotonic()
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.info("CircuitBreaker: HALF_OPEN -> OPEN")
        elif self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.info("CircuitBreaker: CLOSED -> OPEN (failures=%d)", self.failure_count)

    def call(self, fn: Callable[[], T]) -> T:
        if self._should_trip():
            raise CircuitBreakerError("Service unavailable (circuit open)")
        try:
            result = fn()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise


def _retryable(exception):
    if isinstance(exception, grpc.RpcError):
        return exception.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED)
    return False


def _create_jwt() -> str:
    secret = os.environ.get("BOOKING_JWT_SECRET", "shared-secret-change-in-prod")
    return jwt.encode({"service": "booking"}, secret, algorithm="HS256")


def _metadata():
    return [("authorization", f"Bearer {_create_jwt()}")]


# Lazy init
_channel = None
_stub = None
_circuit_breaker = None


def _get_channel():
    global _channel
    if _channel is None:
        addr = os.environ.get("FLIGHT_GRPC_ADDR", "localhost:50051")
        _channel = grpc.insecure_channel(addr)
    return _channel


def _get_stub():
    global _stub
    if _stub is None:
        from generated import flight_service_pb2_grpc
        _stub = flight_service_pb2_grpc.FlightServiceStub(_get_channel())
    return _stub


def _get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker
    if _circuit_breaker is None:
        threshold = int(os.environ.get("CB_FAILURE_THRESHOLD", "5"))
        timeout = float(os.environ.get("CB_RECOVERY_TIMEOUT", "15"))
        success = int(os.environ.get("CB_SUCCESS_THRESHOLD", "1"))
        _circuit_breaker = CircuitBreaker(threshold, timeout, success)
    return _circuit_breaker


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=0.4),
    retry=retry_if_exception(_retryable),
    reraise=True,
)
def _search_flights(origin: str, destination: str, date_str: str | None):
    from generated import flight_service_pb2
    from google.protobuf import timestamp_pb2
    stub = _get_stub()
    req = flight_service_pb2.SearchFlightsRequest(origin=origin, destination=destination)
    if date_str:
        dt = __import__("datetime").datetime.fromisoformat(date_str + "T12:00:00+00:00")
        req.date.seconds = int(dt.timestamp())
    return stub.SearchFlights(req, metadata=_metadata())


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=0.4),
    retry=retry_if_exception(_retryable),
    reraise=True,
)
def _get_flight(flight_id: str):
    from generated import flight_service_pb2
    stub = _get_stub()
    return stub.GetFlight(flight_service_pb2.GetFlightRequest(id=flight_id), metadata=_metadata())


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=0.4),
    retry=retry_if_exception(_retryable),
    reraise=True,
)
def _reserve_seats(flight_id: str, seat_count: int, booking_id: str):
    from generated import flight_service_pb2
    stub = _get_stub()
    return stub.ReserveSeats(
        flight_service_pb2.ReserveSeatsRequest(flight_id=flight_id, seat_count=seat_count, booking_id=booking_id),
        metadata=_metadata(),
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=0.4),
    retry=retry_if_exception(_retryable),
    reraise=True,
)
def _release_reservation(booking_id: str):
    from generated import flight_service_pb2
    stub = _get_stub()
    return stub.ReleaseReservation(flight_service_pb2.ReleaseReservationRequest(booking_id=booking_id), metadata=_metadata())


def search_flights(origin: str, destination: str, date_str: str | None):
    cb = _get_circuit_breaker()
    return cb.call(lambda: _search_flights(origin, destination, date_str))


def get_flight(flight_id: str):
    cb = _get_circuit_breaker()
    return cb.call(lambda: _get_flight(flight_id))


def reserve_seats(flight_id: str, seat_count: int, booking_id: str):
    cb = _get_circuit_breaker()
    return cb.call(lambda: _reserve_seats(flight_id, seat_count, booking_id))


def release_reservation(booking_id: str):
    cb = _get_circuit_breaker()
    return cb.call(lambda: _release_reservation(booking_id))
