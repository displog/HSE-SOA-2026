import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base


class Flight(Base):
    __tablename__ = "flights"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_number = Column(String(20), nullable=False)
    airline = Column(String(100), nullable=False)
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    departure_time = Column(DateTime(timezone=True), nullable=False)
    arrival_time = Column(DateTime(timezone=True), nullable=False)
    total_seats = Column(Integer, nullable=False)
    available_seats = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("total_seats > 0", name="check_total_seats_positive"),
        CheckConstraint("available_seats >= 0", name="check_available_seats_nonneg"),
        CheckConstraint("price > 0", name="check_price_positive"),
        CheckConstraint(
            "available_seats <= total_seats",
            name="check_available_lte_total",
        ),
    )


class SeatReservation(Base):
    __tablename__ = "seat_reservations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flight_id = Column(UUID(as_uuid=True), ForeignKey("flights.id"), nullable=False)
    booking_id = Column(String(64), nullable=False, unique=True)
    seat_count = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("seat_count > 0", name="check_seat_count_positive"),
    )
