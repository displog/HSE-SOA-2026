#!/bin/bash


set -e
cd "$(dirname "$0")"

DOCKER_COMPOSE="docker compose"
if ! $DOCKER_COMPOSE version >/dev/null 2>&1; then
  DOCKER_COMPOSE="docker-compose"
fi

echo "=== Building and starting services ==="
$DOCKER_COMPOSE build
$DOCKER_COMPOSE up -d

echo ""
echo "=== Waiting for services to be ready ==="
sleep 10

echo ""
echo "=== Health check ==="
curl -s http://localhost:8000/health || echo "Booking service not ready yet, wait a bit more"

echo ""
echo "=== Services running. Test from laptop: ==="
echo "  curl http://localhost:8000/flights?origin=SVO&destination=LED&date=2026-04-01"
echo ""
echo "Logs: $DOCKER_COMPOSE logs -f"
