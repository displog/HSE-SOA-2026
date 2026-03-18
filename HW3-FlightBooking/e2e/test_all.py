#!/usr/bin/env python3
"""
E2E-тесты для Flight Booking API.
"""
import argparse
import sys

import requests

BASE_URL = "http://localhost:8001"


def ok(name: str, resp: requests.Response, expected_status: int = 200) -> bool:
    if resp.status_code == expected_status:
        print(f"  OK {name}")
        return True
    print(f"  FAIL {name}: expected {expected_status}, got {resp.status_code}")
    if resp.text:
        print(f"       {resp.text[:300]}")
    return False


def main():
    global BASE_URL
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=BASE_URL, help="Base URL API")
    ap.add_argument("--circuit-breaker", action="store_true",
                    help="Тест Circuit Breaker: останови flight-service и запусти с этим флагом")
    args = ap.parse_args()
    BASE_URL = args.url.rstrip("/")

    fails = 0

    if args.circuit_breaker:
        print("\n--- Circuit Breaker Test ---")
        print("Убедись, что flight-service остановлен: docker compose stop flight-service\n")
        for i in range(8):
            try:
                r = requests.get(f"{BASE_URL}/flights", params={"origin": "SVO", "destination": "LED"}, timeout=3)
                print(f"  Request {i+1}: status={r.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"  Request {i+1}: error (expected) {type(e).__name__}")
        print("\nОжидание: после 5 ошибок — 503. Запусти flight-service, подожди ~15 сек.")
        return 0

    def run_test(name: str, fn):
        nonlocal fails
        print(f"\n--- {name} ---")
        try:
            if not fn():
                fails += 1
        except Exception as e:
            print(f"  EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            fails += 1

    # 1. Health
    run_test("1. Health check", lambda: ok("GET /health", requests.get(f"{BASE_URL}/health")))

    # 2. Поиск рейсов
    def test_search():
        r = requests.get(f"{BASE_URL}/flights", params={"origin": "SVO", "destination": "LED", "date": "2026-04-01"})
        if not ok("GET /flights?origin=SVO&destination=LED&date=2026-04-01", r):
            return False
        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            print("  FAIL: expected non-empty list")
            return False
        print(f"  OK got {len(data)} flight(s)")
        return True
    run_test("2. Поиск рейсов (с датой)", test_search)

    def test_search_no_date():
        r = requests.get(f"{BASE_URL}/flights", params={"origin": "SVO", "destination": "LED"})
        return ok("GET /flights without date", r) and isinstance(r.json(), list)
    run_test("2b. Поиск рейсов (без даты)", test_search_no_date)

    def get_flight_id():
        r = requests.get(f"{BASE_URL}/flights", params={"origin": "SVO", "destination": "LED", "date": "2026-04-01"})
        return r.json()[0]["id"] if r.status_code == 200 and r.json() else None

    # 3. Получение рейса
    def test_get_flight():
        fid = get_flight_id()
        if not fid:
            print("  SKIP: no flights")
            return True
        return ok("GET /flights/{id}", requests.get(f"{BASE_URL}/flights/{fid}"))
    run_test("3. Получение рейса по ID", test_get_flight)

    run_test("3b. Несуществующий рейс (404)", lambda: ok(
        "GET /flights/{bad_id}",
        requests.get(f"{BASE_URL}/flights/00000000-0000-0000-0000-000000000000"), 404
    ))

    # 4. Создание бронирования
    booking_id = [None]  # mutable для closure

    def test_create_booking():
        fid = get_flight_id()
        if not fid:
            return True
        r = requests.post(
            f"{BASE_URL}/bookings",
            json={
                "user_id": "test_user_e2e",
                "flight_id": fid,
                "passenger_name": "Test User",
                "passenger_email": "test@example.com",
                "seat_count": 1,
            },
        )
        if not ok("POST /bookings", r):
            return False
        booking_id[0] = r.json().get("id")
        if not booking_id[0]:
            print("  FAIL: no id in response")
            return False
        print(f"  OK booking_id={booking_id[0]}")
        return True
    run_test("4. Создание бронирования", test_create_booking)

    def test_create_booking_no_seats():
        fid = get_flight_id()
        if not fid:
            return True
        r = requests.post(
            f"{BASE_URL}/bookings",
            json={
                "user_id": "u", "flight_id": fid, "passenger_name": "T",
                "passenger_email": "t@t.com", "seat_count": 99999,
            },
        )
        return ok("POST /bookings (недостаточно мест) -> 400", r, 400)
    run_test("4b. Граничный случай: недостаточно мест (400)", test_create_booking_no_seats)

    run_test("4c. Граничный случай: некорректное тело (422)", lambda: ok(
        "POST /bookings invalid body",
        requests.post(f"{BASE_URL}/bookings", json={"user_id": "u"}), 422
    ))

    run_test("4d. Граничный случай: несуществующий рейс (404)", lambda: ok(
        "POST /bookings bad flight_id",
        requests.post(f"{BASE_URL}/bookings", json={
            "user_id": "u", "flight_id": "00000000-0000-0000-0000-000000000000",
            "passenger_name": "T", "passenger_email": "t@t.com", "seat_count": 1,
        }), 404
    ))

    # 5. Получение бронирования
    def test_get_booking():
        bid = booking_id[0]
        if not bid:
            fid = get_flight_id()
            if not fid:
                return True
            r = requests.post(f"{BASE_URL}/bookings", json={
                "user_id": "u", "flight_id": fid, "passenger_name": "T",
                "passenger_email": "t@t.com", "seat_count": 1,
            })
            if r.status_code != 200:
                return True
            bid = r.json().get("id")
        if not bid:
            return True
        return ok("GET /bookings/{id}", requests.get(f"{BASE_URL}/bookings/{bid}"))
    run_test("5. Получение бронирования", test_get_booking)

    run_test("5b. Граничный случай: несуществующее бронирование (404)", lambda: ok(
        "GET /bookings/{bad_id}",
        requests.get(f"{BASE_URL}/bookings/00000000-0000-0000-0000-000000000000"), 404
    ))

    # 6. Список бронирований
    def test_list_bookings():
        r = requests.get(f"{BASE_URL}/bookings", params={"user_id": "test_user_e2e"})
        return ok("GET /bookings?user_id=X", r) and isinstance(r.json(), list)
    run_test("6. Список бронирований пользователя", test_list_bookings)

    # 7. Отмена бронирования
    def test_cancel():
        bid = booking_id[0]
        if not bid:
            return True
        return ok("POST /bookings/{id}/cancel", requests.post(f"{BASE_URL}/bookings/{bid}/cancel"))
    run_test("7. Отмена бронирования", test_cancel)

    def test_cancel_twice():
        bid = booking_id[0]
        if not bid:
            return True
        return ok("POST cancel (уже отменено) -> 400",
                  requests.post(f"{BASE_URL}/bookings/{bid}/cancel"), 400)
    run_test("7b. Граничный случай: повторная отмена (400)", test_cancel_twice)

    run_test("7c. Граничный случай: отмена несуществующего (404)", lambda: ok(
        "POST cancel bad id",
        requests.post(f"{BASE_URL}/bookings/00000000-0000-0000-0000-000000000000/cancel"), 404
    ))

    # Итог
    print("\n" + "=" * 50)
    if fails == 0:
        print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ")
    else:
        print(f"ПРОВАЛЕНО: {fails} тест(ов)")
    print("=" * 50)
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
