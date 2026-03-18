#!/bin/bash
set -e
cd /app/flight-service
echo "Running migrations..."
alembic upgrade head
echo "Starting Flight Service..."
exec python main.py
