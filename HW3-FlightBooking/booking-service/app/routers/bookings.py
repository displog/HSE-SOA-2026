import uuid

import grpc
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db

from app.models import Booking
from app.schemas import CreateBookingRequest, BookingResponse
from app.flight_client import get_flight, reserve_seats, release_reservation, CircuitBreakerError

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.post("", response_model=BookingResponse)
def create_booking(req: CreateBookingRequest, db: Session = Depends(get_db)):
    try:
        flight_resp = get_flight(req.flight_id)
    except CircuitBreakerError:
        raise HTTPException(status_code=503, detail="Service unavailable")
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Flight not found")
        raise HTTPException(status_code=502, detail=str(e))

    flight = flight_resp.flight
    total_price = req.seat_count * float(flight.price)

    booking_id = str(uuid.uuid4())
    try:
        reserve_seats(req.flight_id, req.seat_count, booking_id)
    except CircuitBreakerError:
        raise HTTPException(status_code=503, detail="Service unavailable")
    except grpc.RpcError as e:
        if e.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
            raise HTTPException(status_code=400, detail="Not enough seats")
        if e.code() == grpc.StatusCode.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Flight not found")
        raise HTTPException(status_code=502, detail=str(e))

    booking = Booking(
        id=uuid.UUID(booking_id),
        user_id=req.user_id,
        flight_id=uuid.UUID(req.flight_id),
        passenger_name=req.passenger_name,
        passenger_email=req.passenger_email,
        seat_count=req.seat_count,
        total_price=total_price,
        status="CONFIRMED",
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)

    return BookingResponse(
        id=str(booking.id),
        user_id=booking.user_id,
        flight_id=str(booking.flight_id),
        passenger_name=booking.passenger_name,
        passenger_email=booking.passenger_email,
        seat_count=booking.seat_count,
        total_price=float(booking.total_price),
        status=booking.status,
    )


@router.get("/{booking_id}", response_model=BookingResponse)
def get_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = db.get(Booking, uuid.UUID(booking_id))
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return BookingResponse(
        id=str(booking.id),
        user_id=booking.user_id,
        flight_id=str(booking.flight_id),
        passenger_name=booking.passenger_name,
        passenger_email=booking.passenger_email,
        seat_count=booking.seat_count,
        total_price=float(booking.total_price),
        status=booking.status,
    )


@router.get("", response_model=list[BookingResponse])
def list_bookings(user_id: str, db: Session = Depends(get_db)):
    bookings = db.execute(select(Booking).where(Booking.user_id == user_id)).scalars().all()
    return [
        BookingResponse(
            id=str(b.id),
            user_id=b.user_id,
            flight_id=str(b.flight_id),
            passenger_name=b.passenger_name,
            passenger_email=b.passenger_email,
            seat_count=b.seat_count,
            total_price=float(b.total_price),
            status=b.status,
        )
        for b in bookings
    ]


@router.post("/{booking_id}/cancel")
def cancel_booking(booking_id: str, db: Session = Depends(get_db)):
    booking = db.get(Booking, uuid.UUID(booking_id))
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status != "CONFIRMED":
        raise HTTPException(status_code=400, detail="Booking is not confirmed")
    try:
        release_reservation(booking_id)
    except CircuitBreakerError:
        raise HTTPException(status_code=503, detail="Service unavailable")
    except grpc.RpcError:
        pass
    booking.status = "CANCELLED"
    db.commit()
    return {"status": "cancelled"}
