#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E2E-сценарии: валидация, ошибки, роли. Запуск: python e2e_scenarios.py [BASE_URL]"""
import sys
import io
import time

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from datetime import datetime, timedelta, timezone

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8002"
SUFFIX = int(time.time()) % 100000


def req(method: str, path: str, token: str | None = None, json_data: dict | None = None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.request(method, url, headers=headers, json=json_data, timeout=10)
    try:
        data = r.json() if r.content else {}
    except Exception:
        data = {"_raw": r.text[:500] if r.text else ""}
    return data, r.status_code


def ok(name: str, data: dict, status: int, expected: int | None = None) -> bool:
    exp = expected if expected is not None else (200 if "успех" in name.lower() else None)
    if exp is not None:
        passed = status == exp
    else:
        passed = 200 <= status < 300
    sym = "[OK]" if passed else "[X]"
    err = (data.get("error_code") or data.get("detail", {}).get("error_code") if isinstance(data.get("detail"), dict) else None) or ""
    print(f"  {sym} {name} [{status}] {err}")
    return passed


def main():
    print("=" * 60)
    print("E2E-сценарии для защиты")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)

    try:
        requests.get(f"{BASE_URL}/docs", timeout=3)
    except requests.exceptions.ConnectionError:
        print("API недоступен")
        sys.exit(1)

    # Регистрация
    tokens = {}
    for role, email in [("USER", f"e2e_user_{SUFFIX}@test.com"), ("SELLER", f"e2e_seller_{SUFFIX}@test.com")]:
        d, s = req("POST", "/auth/register", json_data={"email": email, "password": "pwd123", "role": role})
        if s in (200, 201):
            tokens[role] = d.get("access_token")
        else:
            d, s = req("POST", "/auth/login", json_data={"email": email, "password": "pwd123"})
            tokens[role] = d.get("access_token") if s == 200 else None

    if not tokens.get("SELLER"):
        print("Ошибка: нет токена SELLER")
        return

    # Создать товар
    d, s = req("POST", "/products", token=tokens["SELLER"], json_data={
        "name": f"E2E-товар {SUFFIX}", "price": 100, "stock": 5, "category": "Test", "status": "ACTIVE"
    })
    product_id = d.get("id") if s in (200, 201) else None
    if not product_id:
        print("Товар не создан")
        return

    passed = 0
    total = 0

    # --- Валидация ---
    print("\n1. Валидация (ожидаем 400)")
    cases = [
        ("POST /products name=''", "POST", "/products", tokens["SELLER"], {"name": "", "price": 1, "stock": 1, "category": "X", "status": "ACTIVE"}, 400),
        ("POST /products price=0", "POST", "/products", tokens["SELLER"], {"name": "X", "price": 0, "stock": 1, "category": "X", "status": "ACTIVE"}, 400),
        ("POST /orders items=[]", "POST", "/orders", tokens["USER"], {"items": []}, 400),
    ]
    for name, method, path, tok, body, exp in cases:
        total += 1
        d, s = req(method, path, token=tok, json_data=body)
        if ok(name, d, s, exp):
            passed += 1

    # --- Роли ---
    print("\n2. Роли (USER не может POST /products, ожидаем 403)")
    total += 1
    d, s = req("POST", "/products", token=tokens["USER"], json_data={"name": "X", "price": 1, "stock": 1, "category": "X", "status": "ACTIVE"})
    if ok("USER POST /products", d, s, 403):
        passed += 1

    # --- PRODUCT_NOT_FOUND ---
    print("\n3. PRODUCT_NOT_FOUND (404)")
    total += 1
    d, s = req("GET", "/products/00000000-0000-0000-0000-000000000000", token=tokens["USER"])
    if ok("GET /products/fake-uuid", d, s, 404):
        passed += 1

    # --- Без токена ---
    print("\n4. Без токена (401)")
    total += 1
    d, s = req("GET", "/products")
    if ok("GET /products без токена", d, s, 401):
        passed += 1

    print("\n" + "=" * 60)
    print(f"Итого: {passed}/{total}")
    print("=" * 60)


if __name__ == "__main__":
    main()
