#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Демонстрация Marketplace API. Запуск: python demo.py [BASE_URL]"""
import sys
import io
import time

# Windows: избежать UnicodeEncodeError при выводе в консоль (cp1251)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
from datetime import datetime, timedelta, timezone


try:
    import requests
except ImportError:
    print("Ошибка: модуль requests не найден.")
    print("Установи: pip install requests")
    print("Или: .\\.venv\\Scripts\\pip.exe install requests")
    sys.exit(1)

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8002"
SUFFIX = int(time.time()) % 100000


def req(method: str, path: str, token: str | None = None, json_data: dict | None = None) -> tuple:
    """Выполнить запрос и вернуть JSON."""
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.request(method, url, headers=headers, json=json_data, timeout=10)
    try:
        data = r.json() if r.content else {}
    except Exception:
        data = {"_raw": r.text[:200] if r.text else ""}
    return data, r.status_code


def step(name: str, data: dict, status: int, expected_status: int | None = None):
    """Вывести результат шага. Если expected_status задан, успех = (status == expected_status)."""
    if expected_status is not None:
        ok = status == expected_status
    else:
        ok = 200 <= status < 300
    sym = "[OK]" if ok else "[X]"
    print(f"  {sym} {name} [{status}]", flush=True)
    if not ok and isinstance(data, dict):
        err = data.get("detail") or data.get("message") or data
        if err:
            print(f"      {err}", flush=True)
    return ok


def main():
    print("=" * 60, flush=True)
    print("Marketplace API — демонстрация функционала", flush=True)
    print(f"Base URL: {BASE_URL}", flush=True)
    print("=" * 60, flush=True)

    # Проверка доступности API
    try:
        r = requests.get(f"{BASE_URL}/docs", timeout=3)
    except requests.exceptions.ConnectionError:
        print("\nОшибка: API недоступен. Запустите docker compose up --build -d", flush=True)
        sys.exit(1)

    tokens = {}
    product_id = None
    order_id = None

    # --- 1. Auth: регистрация ---
    print("\n1. Регистрация пользователей (USER, SELLER, ADMIN)", flush=True)
    for role, email in [
        ("USER", f"demo_user_{SUFFIX}@test.com"),
        ("SELLER", f"demo_seller_{SUFFIX}@test.com"),
        ("ADMIN", f"demo_admin_{SUFFIX}@test.com"),
    ]:
        data, status = req("POST", "/auth/register", json_data={
            "email": email,
            "password": "password123",
            "role": role,
        })
        if step(f"Register {role}", data, status):
            tokens[role] = data.get("access_token")
        else:
            # Возможно уже зарегистрирован — логин
            data, status = req("POST", "/auth/login", json_data={"email": email, "password": "password123"})
            if step(f"Login {role}", data, status):
                tokens[role] = data.get("access_token")

    if not tokens.get("SELLER"):
        print("  Ошибка: нужен токен SELLER", flush=True)
        return

    # --- 2. Products: создание ---
    print("\n2. Создание товара (SELLER)", flush=True)
    data, status = req("POST", "/products", token=tokens["SELLER"], json_data={
        "name": f"Демо-товар {SUFFIX}",
        "description": "Описание демо-товара",
        "price": 1999.99,
        "stock": 10,
        "category": "Электроника",
        "status": "ACTIVE",
    })
    if step("POST /products", data, status):
        product_id = data.get("id")
        print(f"      product_id = {product_id}", flush=True)

    if not product_id:
        print("  Ошибка: товар не создан", flush=True)
        return

    # --- 3. Products: список и получение ---
    print("\n3. Список и получение товара", flush=True)
    data, status = req("GET", "/products?page=0&size=5", token=tokens["USER"])
    step("GET /products", data, status)

    data, status = req("GET", f"/products/{product_id}", token=tokens["USER"])
    step("GET /products/{id}", data, status)

    # --- 4. Orders: создание ---
    print("\n4. Создание заказа (USER)", flush=True)
    data, status = req("POST", "/orders", token=tokens["USER"], json_data={
        "items": [{"product_id": product_id, "quantity": 2}],
    })
    if step("POST /orders", data, status):
        order_id = data.get("id")
        print(f"      order_id = {order_id}, total = {data.get('total_amount')}", flush=True)

    # --- 5. Orders: получение и обновление ---
    if order_id:
        print("\n5. Получение и обновление заказа", flush=True)
        data, status = req("GET", f"/orders/{order_id}", token=tokens["USER"])
        step("GET /orders/{id}", data, status)

        data, status = req("PUT", f"/orders/{order_id}", token=tokens["USER"], json_data={
            "items": [{"product_id": product_id, "quantity": 1}],
        })
        step("PUT /orders/{id}", data, status)

    # --- 6. Promo-codes: создание ---
    print("\n6. Создание промокода (SELLER)", flush=True)
    now = datetime.now(timezone.utc)
    valid_from = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    valid_until = (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S")
    data, status = req("POST", "/promo-codes", token=tokens["SELLER"], json_data={
        "code": f"DEMO{SUFFIX}",
        "discount_type": "PERCENTAGE",
        "discount_value": 15,
        "min_order_amount": 100,
        "max_uses": 50,
        "valid_from": valid_from,
        "valid_until": valid_until,
        "active": True,
    })
    promo_code = f"DEMO{SUFFIX}"
    if isinstance(data, dict) and data.get("code"):
        promo_code = data["code"]
    step("POST /promo-codes", data, status)

    # --- 7. Order с промокодом (другой USER, т.к. у первого активный заказ) ---
    print("\n7. Заказ с промокодом (ADMIN, т.к. у USER уже есть активный заказ)", flush=True)
    data, status = req("POST", "/orders", token=tokens["ADMIN"], json_data={
        "items": [{"product_id": product_id, "quantity": 1}],
        "promo_code": promo_code,
    })
    order2_id = data.get("id") if isinstance(data, dict) and 200 <= status < 300 else None
    step("POST /orders + promo", data, status)
    if order2_id:
        print(f"      order_id = {order2_id}, discount = {data.get('discount_amount')}", flush=True)

    # --- 8. Отмена заказа ---
    print("\n8. Отмена заказа", flush=True)
    if order_id:
        data, status = req("POST", f"/orders/{order_id}/cancel", token=tokens["USER"])
        step("POST /orders/{id}/cancel", data, status)

    # --- 9. Products: обновление и soft delete ---
    print("\n9. Обновление и удаление товара", flush=True)
    data, status = req("PUT", f"/products/{product_id}", token=tokens["SELLER"], json_data={
        "name": f"Обновлённый товар {SUFFIX}",
        "description": "Новое описание",
        "price": 2499.99,
        "stock": 8,
        "category": "Электроника",
        "status": "ACTIVE",
    })
    step("PUT /products/{id}", data, status)

    data, status = req("DELETE", f"/products/{product_id}", token=tokens["SELLER"])
    step("DELETE /products/{id} (soft)", data, status)

    # --- 10. Refresh token ---
    print("\n10. Обновление токена (refresh)", flush=True)
    data, status = req("POST", "/auth/login", json_data={
        "email": f"demo_user_{SUFFIX}@test.com",
        "password": "password123",
    })
    refresh_tok = data.get("refresh_token") if isinstance(data, dict) else None
    if refresh_tok:
        data, status = req("POST", "/auth/refresh", json_data={"refresh_token": refresh_tok})
        step("POST /auth/refresh", data, status)

    # --- 11. Проверка ролей (403) ---
    print("\n11. Проверка ролей (ожидаем 403)", flush=True)
    data, status = req("POST", "/products", token=tokens["USER"], json_data={
        "name": "Test",
        "price": 1,
        "stock": 1,
        "category": "X",
        "status": "ACTIVE",
    })
    if step("USER не может POST /products (403)", data, status, expected_status=403):
        print("      ACCESS_DENIED — корректно", flush=True)

    print("\n" + "=" * 60, flush=True)
    print("Демонстрация завершена.", flush=True)
    print("Проверь логи uvicorn — там JSON с request_id, duration_ms и т.д.", flush=True)
    print("=" * 60, flush=True)


if __name__ == "__main__":
    main()
