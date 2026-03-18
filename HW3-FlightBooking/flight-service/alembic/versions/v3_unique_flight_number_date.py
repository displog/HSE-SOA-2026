"""add unique flight_number departure_date

Revision ID: v3
Revises: v2
Create Date: 2026-03-04

"""
from typing import Sequence, Union

from alembic import op

revision: str = "v3"
down_revision: Union[str, None] = "v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE UNIQUE INDEX uq_flight_number_departure_date
        ON flights (flight_number, (departure_time::date))
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_flight_number_departure_date")
