"""initial schema

Revision ID: v1
Revises:
Create Date: 2026-03-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "v1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "flights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("flight_number", sa.String(20), nullable=False),
        sa.Column("airline", sa.String(100), nullable=False),
        sa.Column("origin", sa.String(3), nullable=False),
        sa.Column("destination", sa.String(3), nullable=False),
        sa.Column("departure_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrival_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_seats", sa.Integer(), nullable=False),
        sa.Column("available_seats", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("total_seats > 0", name="check_total_seats_positive"),
        sa.CheckConstraint("available_seats >= 0", name="check_available_seats_nonneg"),
        sa.CheckConstraint("price > 0", name="check_price_positive"),
    )
    op.create_index(
        "ix_flights_origin_destination_departure",
        "flights",
        ["origin", "destination", "departure_time"],
        unique=False,
    )

    op.create_table(
        "seat_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("flight_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("booking_id", sa.String(64), nullable=False),
        sa.Column("seat_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["flight_id"], ["flights.id"]),
        sa.UniqueConstraint("booking_id", name="uq_seat_reservations_booking_id"),
        sa.CheckConstraint("seat_count > 0", name="check_seat_count_positive"),
    )
    op.create_index(
        "ix_seat_reservations_booking_id",
        "seat_reservations",
        ["booking_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("seat_reservations")
    op.drop_table("flights")
