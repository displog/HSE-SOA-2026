import grpc
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.flight_client import search_flights, get_flight, CircuitBreakerError
from app.schemas import FlightResponse

router = APIRouter(prefix="/flights", tags=["flights"])


def _proto_flight_to_response(f) -> FlightResponse:
    dep = datetime.fromtimestamp(f.departure_time.seconds, tz=timezone.utc) if f.departure_time.seconds else ""
    arr = datetime.fromtimestamp(f.arrival_time.seconds, tz=timezone.utc) if f.arrival_time.seconds else ""
    return FlightResponse(
        id=f.id,
        flight_number=f.flight_number,
        airline=f.airline,
        origin=f.origin,
        destination=f.destination,
        departure_time=dep.isoformat() if dep else "",
        arrival_time=arr.isoformat() if arr else "",
        total_seats=f.total_seats,
        available_seats=f.available_seats,
        price=f.price,
        status="SCHEDULED" if f.status == 1 else str(f.status),
    )


@router.get("", response_model=list[FlightResponse])
def list_flights(origin: str, destination: str, date: str | None = None):
    try:
        resp = search_flights(origin, destination, date)
    except CircuitBreakerError:
        raise HTTPException(status_code=503, detail="Service unavailable")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return [_proto_flight_to_response(f) for f in resp.flights]


@router.get("/{flight_id}", response_model=FlightResponse)
def get_flight_by_id(flight_id: str):
    try:
        resp = get_flight(flight_id)
    except CircuitBreakerError:
        raise HTTPException(status_code=503, detail="Service unavailable")
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Flight not found")
        raise HTTPException(status_code=502, detail=str(e))
    if not resp.flight:
        raise HTTPException(status_code=404, detail="Flight not found")
    return _proto_flight_to_response(resp.flight)
