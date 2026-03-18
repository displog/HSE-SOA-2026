import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Numeric, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(64), nullable=False)
    flight_id = Column(UUID(as_uuid=True), nullable=False)
    passenger_name = Column(String(255), nullable=False)
    passenger_email = Column(String(255), nullable=False)
    seat_count = Column(Integer, nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("seat_count > 0", name="check_seat_count_positive"),
        CheckConstraint("total_price > 0", name="check_total_price_positive"),
    )
