# src/db.py
import os
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session as SQLModelSession

# Ищем .env: catalog-service/, HW2-OpenAPI/, корень проекта, cwd
_base = Path(__file__).resolve().parent.parent  # catalog-service/
# Явная загрузка catalog-service/.env первой (надёжно при запуске из корня)
_env_catalog = _base / ".env"
if _env_catalog.exists():
    load_dotenv(_env_catalog)
for p in [_base, _base.parent, Path.cwd()]:
    env_file = p / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        break
else:
    load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in .env file")

engine = create_engine(
    DATABASE_URL,
    echo=True,                      # логи SQL-запросов — удобно для отладки
    pool_pre_ping=True,             # проверка соединения перед использованием
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=SQLModelSession
)


def get_db() -> Generator[SQLModelSession, None, None]:
    """Dependency для получения сессии БД в эндпоинтах"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()