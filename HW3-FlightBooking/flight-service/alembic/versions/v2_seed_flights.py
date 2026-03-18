"""seed flights

Revision ID: v2
Revises: v1
Create Date: 2026-03-04

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa

revision: str = "v2"
down_revision: Union[str, None] = "v1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    id1 = str(uuid.uuid4())
    id2 = str(uuid.uuid4())
    op.execute(sa.text(f"""
        INSERT INTO flights (id, flight_number, airline, origin, destination, departure_time, arrival_time, total_seats, available_seats, price, status)
        VALUES 
        ('{id1}', 'SU1234', 'Aeroflot', 'SVO', 'LED', '2026-04-01 10:00:00+00', '2026-04-01 11:30:00+00', 180, 180, 5500.00, 'SCHEDULED'),
        ('{id2}', 'SU5678', 'Aeroflot', 'VKO', 'SVO', '2026-04-02 08:00:00+00', '2026-04-02 09:00:00+00', 120, 120, 3200.00, 'SCHEDULED')
    """))


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM flights WHERE flight_number IN ('SU1234', 'SU5678')"))
