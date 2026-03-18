#!/bin/bash
set -e
cd /app/booking-service
echo "Running migrations..."
alembic upgrade head
echo "Starting Booking Service..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
