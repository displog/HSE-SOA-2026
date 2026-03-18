import logging
import uuid
from datetime import datetime

import grpc
from sqlalchemy import select
from sqlalchemy.orm import Session
from google.protobuf import timestamp_pb2

from app.db import SessionLocal
from app.models import Flight, SeatReservation
from app.redis_cache import (
    get_cached_flight,
    set_cached_flight,
    get_cached_search,
    set_cached_search,
    invalidate_flight,
    invalidate_search,
)

# Will be set after generated module is available
generated = None

logger = logging.getLogger(__name__)

# Status mapping
PROTO_STATUS = {
    "SCHEDULED": 1,
    "DEPARTED": 2,
    "CANCELLED": 3,
    "COMPLETED": 4,
}
STATUS_TO_PROTO = {v: k for k, v in PROTO_STATUS.items()}


def _dt_to_proto(dt: datetime) -> timestamp_pb2.Timestamp:
    t = timestamp_pb2.Timestamp()
    t.seconds = int(dt.timestamp())
    t.nanos = int((dt.timestamp() % 1) * 1e9)
    return t


def _flight_to_proto(f: Flight):
    flight_pb2 = generated.flight_service_pb2
    return flight_pb2.Flight(
        id=str(f.id),
        flight_number=f.flight_number,
        airline=f.airline,
        origin=f.origin,
        destination=f.destination,
        departure_time=_dt_to_proto(f.departure_time),
        arrival_time=_dt_to_proto(f.arrival_time),
        total_seats=f.total_seats,
        available_seats=f.available_seats,
        price=float(f.price),
        status=PROTO_STATUS.get(f.status, 0),
    )


def _flight_to_cache_dict(f: Flight) -> dict:
    return {
        "id": str(f.id),
        "flight_number": f.flight_number,
        "airline": f.airline,
        "origin": f.origin,
        "destination": f.destination,
        "departure_time": f.departure_time.isoformat(),
        "arrival_time": f.arrival_time.isoformat(),
        "total_seats": f.total_seats,
        "available_seats": f.available_seats,
        "price": str(f.price),
        "status": f.status,
    }


def _cache_dict_to_proto(d: dict):
    flight_pb2 = generated.flight_service_pb2
    from datetime import datetime
    dep = datetime.fromisoformat(d["departure_time"].replace("Z", "+00:00"))
    arr = datetime.fromisoformat(d["arrival_time"].replace("Z", "+00:00"))
    return flight_pb2.Flight(
        id=d["id"],
        flight_number=d["flight_number"],
        airline=d["airline"],
        origin=d["origin"],
        destination=d["destination"],
        departure_time=_dt_to_proto(dep),
        arrival_time=_dt_to_proto(arr),
        total_seats=d["total_seats"],
        available_seats=d["available_seats"],
        price=float(d["price"]),
        status=PROTO_STATUS.get(d["status"], 0),
    )


def _search_cache_to_proto_list(data: list) -> list:
    flight_pb2 = generated.flight_service_pb2
    result = []
    for d in data:
        from datetime import datetime
        dep = datetime.fromisoformat(d["departure_time"].replace("Z", "+00:00"))
        arr = datetime.fromisoformat(d["arrival_time"].replace("Z", "+00:00"))
        result.append(flight_pb2.Flight(
            id=d["id"],
            flight_number=d["flight_number"],
            airline=d["airline"],
            origin=d["origin"],
            destination=d["destination"],
            departure_time=_dt_to_proto(dep),
            arrival_time=_dt_to_proto(arr),
            total_seats=d["total_seats"],
            available_seats=d["available_seats"],
            price=float(d["price"]),
            status=PROTO_STATUS.get(d["status"], 0),
        ))
    return result


class FlightServicer:
    def SearchFlights(self, request, context):
        from generated import flight_service_pb2, flight_service_pb2_grpc
        global generated
        if generated is None:
            generated = __import__("generated", fromlist=["flight_service_pb2", "flight_service_pb2_grpc"])

        origin = request.origin
        destination = request.destination
        date_str = ""
        if request.HasField("date") and request.date.seconds:
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(request.date.seconds, tz=timezone.utc)
            date_str = dt.strftime("%Y-%m-%d")

        if date_str:
            cached = get_cached_search(origin, destination, date_str)
            if cached:
                return generated.flight_service_pb2.SearchFlightsResponse(flights=_search_cache_to_proto_list(cached))

        db: Session = SessionLocal()
        try:
            q = (
                select(Flight)
                .where(Flight.origin == origin)
                .where(Flight.destination == destination)
                .where(Flight.status == "SCHEDULED")
            )
            if date_str:
                start = datetime.fromisoformat(date_str + "T00:00:00+00:00")
                end = datetime.fromisoformat(date_str + "T23:59:59+00:00")
                q = q.where(Flight.departure_time >= start).where(Flight.departure_time <= end)
            flights = db.execute(q).scalars().all()
            result = [_flight_to_proto(f) for f in flights]
            cache_data = [_flight_to_cache_dict(f) for f in flights]
            if date_str:
                set_cached_search(origin, destination, date_str, cache_data)
            return generated.flight_service_pb2.SearchFlightsResponse(flights=result)
        finally:
            db.close()

    def GetFlight(self, request, context):
        from generated import flight_service_pb2, flight_service_pb2_grpc
        global generated
        if generated is None:
            generated = __import__("generated", fromlist=["flight_service_pb2", "flight_service_pb2_grpc"])

        flight_id = request.id
        cached = get_cached_flight(flight_id)
        if cached:
            return generated.flight_service_pb2.GetFlightResponse(flight=_cache_dict_to_proto(cached))

        db: Session = SessionLocal()
        try:
            flight_uuid = uuid.UUID(flight_id)
            flight = db.execute(select(Flight).where(Flight.id == flight_uuid)).scalar_one_or_none()
            if not flight:
                context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")
            set_cached_flight(flight_id, _flight_to_cache_dict(flight))
            return generated.flight_service_pb2.GetFlightResponse(flight=_flight_to_proto(flight))
        finally:
            db.close()

    def ReserveSeats(self, request, context):
        from generated import flight_service_pb2, flight_service_pb2_grpc
        global generated
        if generated is None:
            generated = __import__("generated", fromlist=["flight_service_pb2", "flight_service_pb2_grpc"])

        flight_id = request.flight_id
        seat_count = request.seat_count
        booking_id = request.booking_id

        db: Session = SessionLocal()
        try:
            # Idempotency: if reservation already exists for this booking_id, return OK
            existing = db.execute(
                select(SeatReservation).where(SeatReservation.booking_id == booking_id)
            ).scalars().first()
            if existing and existing.status == "ACTIVE":
                return generated.flight_service_pb2.ReserveSeatsResponse(reservation_id=str(existing.id))

            flight_uuid = uuid.UUID(flight_id)
            flight = db.execute(
                select(Flight).where(Flight.id == flight_uuid).with_for_update()
            ).scalar_one_or_none()
            if not flight:
                context.abort(grpc.StatusCode.NOT_FOUND, "Flight not found")
            if flight.available_seats < seat_count:
                context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, "Not enough seats")
            flight.available_seats -= seat_count
            reservation = SeatReservation(
                flight_id=flight_uuid,
                booking_id=booking_id,
                seat_count=seat_count,
                status="ACTIVE",
            )
            db.add(reservation)
            db.commit()

            invalidate_flight(str(flight_id))
            invalidate_search(flight.origin, flight.destination, flight.departure_time.strftime("%Y-%m-%d"))
            return generated.flight_service_pb2.ReserveSeatsResponse(reservation_id=str(reservation.id))
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    def ReleaseReservation(self, request, context):
        from generated import flight_service_pb2, flight_service_pb2_grpc
        global generated
        if generated is None:
            generated = __import__("generated", fromlist=["flight_service_pb2", "flight_service_pb2_grpc"])

        booking_id = request.booking_id
        db: Session = SessionLocal()
        try:
            reservation = db.execute(
                select(SeatReservation, Flight)
                .join(Flight, SeatReservation.flight_id == Flight.id)
                .where(SeatReservation.booking_id == booking_id)
                .where(SeatReservation.status == "ACTIVE")
                .with_for_update()
            ).first()
            if not reservation:
                context.abort(grpc.StatusCode.NOT_FOUND, "Reservation not found")
            res, flight = reservation
            flight.available_seats += res.seat_count
            res.status = "RELEASED"
            db.commit()

            invalidate_flight(str(flight.id))
            invalidate_search(flight.origin, flight.destination, flight.departure_time.strftime("%Y-%m-%d"))
            return generated.flight_service_pb2.ReleaseReservationResponse()
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()
