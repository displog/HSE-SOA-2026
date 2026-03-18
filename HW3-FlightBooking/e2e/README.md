# E2E тесты

```bash
cd e2e
pip install -r requirements.txt
python test_all.py
```

Другой URL:

```bash
python test_all.py --url http://localhost:8001
```

## Тест Circuit Breaker

1. Запуск сервиса: `docker compose stop flight-service`
2. Запуск: `python test_all.py --circuit-breaker`
3. Подождать ~15 сек, потом : `docker compose start flight-service`
4. Снова вызовать API — должен вернуться в CLOSED
