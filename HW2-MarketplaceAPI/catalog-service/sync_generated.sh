#!/bin/bash
# Синхронизация сгенерированного кода из контейнера в локальную папку.
# Запускать после: docker compose up --build -d
# Результат: src/openapi_server/ и src/schemas/generated.py появятся в проекте (для IDE).

set -e

CONTAINER="marketplace-catalog"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "Ошибка: контейнер ${CONTAINER} не запущен."
    echo "Сначала выполните: cd ../for-docker && docker compose up --build -d"
    exit 1
fi

echo "Копирование openapi_server..."
docker cp "${CONTAINER}:/app/src/openapi_server" ./src/

echo "Копирование generated.py..."
mkdir -p src/schemas
docker cp "${CONTAINER}:/app/src/schemas/generated.py" ./src/schemas/

echo "Готово. Сгенерированные файлы доступны в src/openapi_server/ и src/schemas/generated.py"
echo "(Они в .gitignore и не коммитятся)"
