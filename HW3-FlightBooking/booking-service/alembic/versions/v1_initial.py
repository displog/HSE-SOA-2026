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
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("flight_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("passenger_name", sa.String(255), nullable=False),
        sa.Column("passenger_email", sa.String(255), nullable=False),
        sa.Column("seat_count", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("seat_count > 0", name="check_seat_count_positive"),
        sa.CheckConstraint("total_price > 0", name="check_total_price_positive"),
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("bookings")
