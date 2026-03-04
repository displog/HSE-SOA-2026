# Marketplace API (ДЗ №2: OpenAPI + CRUD)

## Запуск

```bash
cd for-docker
cp .env.example .env
docker compose up --build -d
```

- **API:** [http://localhost:8002](http://localhost:8002)  
- **Swagger:** [http://localhost:8002/docs](http://localhost:8002/docs)  
- **pgAdmin:** [http://localhost:5052](http://localhost:5052) ([admin@example.com](mailto:admin@example.com) / admin)

## E2E-тесты

```bash
cd e2e
pip install -r requirements.txt
python demo.py http://localhost:8002
python e2e_scenarios.py http://localhost:8002
```

## Запуск

1. Клонировать или обновить репозиторий:
  ```bash
   git clone https://github.com/displog/hw2.git
   cd hw2
   # или, если уже клонировано:
   git pull origin main
  ```
2. Запустить стек:
  ```bash
   cd for-docker
   cp .env.example .env
   docker compose up --build -d
  ```
3. Дождаться запуска (Flyway, catalog-service). API: [http://localhost:8002](http://localhost:8002) (или IP хоста:8002, если доступ извне).
4. E2E с того же хоста:
  ```bash
   cd e2e
   pip install -r requirements.txt
   python demo.py http://localhost:8002
   python e2e_scenarios.py http://localhost:8002
  ```
5. Таблицы в БД — через pgAdmin ([http://localhost:5052](http://localhost:5052)) или `psql` к контейнеру postgres.

## Структура

- **catalog-service/** — приложение (OpenAPI, кодогенерация, CRUD)
- **for-docker/** — docker-compose (PostgreSQL, Flyway, pgAdmin)
- **e2e/** — скрипты проверки

