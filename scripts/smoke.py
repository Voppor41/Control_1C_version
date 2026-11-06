#!/usr/bin/env python3
"""Повторный прогон основных сценариев ТЗ после миграции и наполнения.

Запуск: python scripts/smoke.py
Адрес задаётся переменной BASE_URL, по умолчанию http://127.0.0.1:8000.
"""


from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, time as clock, timedelta
from urllib.parse import urlencode

BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
STAMP = int(time.time())


class SmokeError(SystemExit):
    """Останавливает прогон с ненулевым кодом и текстом, какой шаг сломался."""
    pass


def request(method: str, path: str, token: str | None = None, body=None, expected: int | tuple[int, ...] = 200):
    """HTTP-запрос к API. expected — допустимые коды, тело разбирается как JSON."""
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        status = exc.code
    if isinstance(expected, int):
        expected = (expected,)
    if status not in expected:
        raise SmokeError(f"{method} {path} -> {status}, expected {expected}: {raw[:500]!r}")
    if not raw:
        return None
    return json.loads(raw)


def ok(label: str) -> None:
    """Печатает успешный шаг."""
    print(f"OK {label}")


def login(email: str, password: str) -> str:
    """Возвращает access_token демо-пользователя."""
    payload = request("POST", "/api/auth/login", body={"email": email, "password": password})
    if not payload.get("access_token") or not payload.get("role"):
        raise SmokeError(f"login payload missing token: {payload}")
    return payload["access_token"]


def main() -> None:
    """Проходит требования 1–5 на отдельных данных и читает демо-строки Ромашки и Василька."""
    for _ in range(30):
        try:
            health = request("GET", "/health")
            break
        except (urllib.error.URLError, SmokeError):
            time.sleep(1)
    else:
        raise SmokeError(f"API did not become ready at {BASE}/health")
    if health.get("status") != "ok" or health.get("database") != "ok":
        raise SmokeError(f"unhealthy: {health}")
    ok("GET /health")

    ready = request("GET", "/health/ready")
    if not ready.get("demo_seeded") or ready.get("status") != "ok":
        raise SmokeError(f"not ready: {ready}")
    ok("GET /health/ready demo seed")

    spec = request("GET", "/openapi.json")
    for path in (
        "/health",
        "/health/ready",
        "/api/auth/login",
        "/api/users",
        "/api/clients",
        "/api/configurations",
        "/api/version-checks/run",
        "/api/version-checks/outdated",
        "/api/notifications",
        "/api/update-slots/dates",
        "/api/scheduled-updates",
        "/api/reports/updated-clients",
        "/api/reports/updates",
        "/api/reports/outdated-clients",
    ):
        if path not in spec["paths"]:
            raise SmokeError(f"openapi missing {path}")
    docs = urllib.request.Request(BASE + "/docs")
    with urllib.request.urlopen(docs, timeout=30) as response:
        if response.status != 200:
            raise SmokeError("docs are not served")
    ok("openapi and /docs")

    request("POST", "/api/auth/login", body={"email": "admin@example.com", "password": "nope"}, expected=401)
    admin = login("admin@example.com", "admin123")
    specialist = login("specialist@example.com", "specialist123")
    manager = login("manager@example.com", "manager123")
    client = login("client@example.com", "client123")
    me = request("GET", "/api/auth/me", client)
    if me["role"] != "client":
        raise SmokeError(me)
    ok("auth four roles")

    request("POST", "/api/users", client, {"full_name": "X", "email": "x@example.com", "password": "secret12", "role": "client"}, expected=403)
    request("POST", "/api/users", specialist, {"full_name": "X", "email": "x@example.com", "password": "secret12", "role": "specialist"}, expected=403)
    request("POST", "/api/clients", manager, {"company_name": "Nope", "phone": "+70000000000", "email": "nope@example.com"}, expected=403)
    request("GET", "/api/reports/updates", client, expected=403)
    ok("role guards")

    users = request("GET", "/api/users?" + urlencode({"q": "Мария", "role": "specialist"}), admin)
    if users["total"] < 1:
        raise SmokeError(users)
    roles = request("GET", "/api/roles", admin)
    if {item["code"] for item in roles} != {"admin", "specialist", "manager", "client"}:
        raise SmokeError(roles)
    ok("1.1 users and roles")

    clients = request("GET", "/api/clients?" + urlencode({"q": "Ромашка"}), specialist)
    if clients["total"] < 1:
        raise SmokeError(clients)
    romashka = clients["items"][0]["id"]
    configs = request("GET", "/api/configurations?" + urlencode({"q": "Бухгалтерия"}), specialist)
    if configs["total"] < 1 or not configs["items"][0]["current_version"]:
        raise SmokeError(configs)
    installed = request("GET", f"/api/clients/{romashka}/configurations", specialist)
    if not any(item["is_outdated"] for item in installed["items"]):
        raise SmokeError(installed)
    ok("1.2–1.4 demo clients and configurations")

    company = f"ООО Проверка {STAMP}"
    created_client = request(
        "POST",
        "/api/clients",
        specialist,
        {
            "company_name": company,
            "phone": f"+7{STAMP}",
            "email": f"smoke-co-{STAMP}@example.com",
        },
        expected=201,
    )
    blank = request(
        "POST",
        "/api/clients",
        admin,
        {
            "company_name": f"ООО Пустая {STAMP}",
            "phone": f"+8{STAMP}",
            "email": f"blank-{STAMP}@example.com",
        },
        expected=201,
    )
    portal = request(
        "POST",
        "/api/users",
        admin,
        {
            "full_name": f"Клиент {STAMP}",
            "email": f"smoke-{STAMP}@example.com",
            "password": "smoke12345",
            "role": "client",
            "client_id": created_client["id"],
        },
        expected=201,
    )
    if portal["role"] != "client" or portal["client_id"] != created_client["id"]:
        raise SmokeError(portal)
    configuration = request(
        "POST",
        "/api/configurations",
        specialist,
        {"name": f"СмоукКонфигурация {STAMP}", "description": "smoke"},
        expected=201,
    )
    old = request(
        "POST",
        f"/api/configurations/{configuration['id']}/versions",
        specialist,
        {"version": "1.0.0", "is_current": False, "released_at": "2025-01-01"},
        expected=201,
    )
    current = request(
        "POST",
        f"/api/configurations/{configuration['id']}/versions",
        specialist,
        {"version": "1.0.1", "is_current": True, "released_at": "2026-01-01"},
        expected=201,
    )
    if not current["is_current"] or old["is_current"]:
        fresh_old = request("GET", f"/api/configurations/{configuration['id']}", specialist)
        old_flag = next(item for item in fresh_old["versions"] if item["version"] == "1.0.0")
        if old_flag["is_current"] or not current["is_current"]:
            raise SmokeError(fresh_old)
    installation = request(
        "POST",
        f"/api/clients/{created_client['id']}/configurations",
        specialist,
        {
            "configuration_id": configuration["id"],
            "installed_version_id": old["id"],
            "infobase_name": f"smoke_{STAMP}",
        },
        expected=201,
    )
    if installation["is_outdated"] is not True:
        raise SmokeError(installation)
    ok("1.2–1.4 create client, user, configuration, installation")

    run = request(
        "POST",
        "/api/version-checks/run",
        specialist,
        {"client_configuration_id": installation["id"]},
        expected=201,
    )
    if len(run["created"]) != 1 or run["created"][0]["is_outdated"] is not True:
        raise SmokeError(run)
    history = request(
        "GET",
        "/api/version-checks?" + urlencode({"client_configuration_id": installation["id"], "is_outdated": "true"}),
        specialist,
    )
    if history["total"] < 1:
        raise SmokeError(history)
    ok("2.1 and 2.3 version check history")

    outdated = request("GET", "/api/version-checks/outdated?" + urlencode({"q": company}), specialist)
    if outdated["total_clients"] != 1:
        raise SmokeError(outdated)
    demo_outdated = request("GET", "/api/version-checks/outdated?" + urlencode({"q": "Ромашка"}), specialist)
    if demo_outdated["total_clients"] < 1:
        raise SmokeError(demo_outdated)
    ok("2.2 clients needing an update")

    notes = request(
        "POST",
        "/api/notifications",
        specialist,
        {"client_id": created_client["id"], "client_configuration_id": installation["id"]},
        expected=201,
    )
    if len(notes) != 1 or notes[0]["type"] != "update_available":
        raise SmokeError(notes)
    portal_token = login(f"smoke-{STAMP}@example.com", "smoke12345")
    inbox = request("GET", "/api/notifications", portal_token)
    if inbox["unread"] < 1 or not any(item["id"] == notes[0]["id"] for item in inbox["items"]):
        raise SmokeError(inbox)
    read = request("POST", f"/api/notifications/{notes[0]['id']}/read", portal_token)
    if read["is_read"] is not True:
        raise SmokeError(read)
    ok("3.1–3.3 notification delivered to the client")

    slot_day = date.today() + timedelta(days=30 + (STAMP % 400))
    hour = 8 + (STAMP % 9)
    minute = (STAMP // 9) % 60
    second = (STAMP // 500) % 60
    start = clock(hour, minute, second)
    end = clock(hour + 1, minute, second)
    slot = request(
        "POST",
        "/api/update-slots",
        specialist,
        {
            "slot_date": slot_day.isoformat(),
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "capacity": 1,
        },
        expected=201,
    )
    dates = request(
        "GET",
        "/api/update-slots/dates?" + urlencode({"date_from": slot_day.isoformat(), "date_to": slot_day.isoformat()}),
        portal_token,
    )
    if not any(item["slot_date"] == slot_day.isoformat() for item in dates):
        raise SmokeError(dates)
    ok("4.1 available dates")

    booked = request(
        "POST",
        "/api/scheduled-updates",
        portal_token,
        {"client_configuration_id": installation["id"], "slot_id": slot["id"], "comment": "smoke"},
        expected=201,
    )
    if booked["status"] != "scheduled" or booked["slot_date"] != slot_day.isoformat():
        raise SmokeError(booked)
    if not booked["status_history"]:
        raise SmokeError(booked)
    ok("4.2 client picked a date")

    planned = request(
        "GET",
        "/api/scheduled-updates?" + urlencode({"status": "scheduled", "q": company}),
        specialist,
    )
    if planned["total"] < 1:
        raise SmokeError(planned)
    detail = request("GET", f"/api/scheduled-updates/{booked['id']}", specialist)
    if detail["company_name"] != company:
        raise SmokeError(detail)
    ok("4.3 staff list and view")

    progress = request(
        "PATCH",
        f"/api/scheduled-updates/{booked['id']}/status",
        specialist,
        {"status": "in_progress"},
    )
    if progress["status"] != "in_progress":
        raise SmokeError(progress)
    done = request(
        "PATCH",
        f"/api/scheduled-updates/{booked['id']}/status",
        specialist,
        {"status": "completed", "comment": "установлено"},
    )
    if done["status"] != "completed" or done["target_version"] != "1.0.1":
        raise SmokeError(done)
    if not any(item["new_status"] == "completed" for item in done["status_history"]):
        raise SmokeError(done)
    request(
        "PATCH",
        f"/api/scheduled-updates/{booked['id']}/status",
        specialist,
        {"status": "requested"},
        expected=409,
    )
    refreshed = request("GET", f"/api/client-configurations/{installation['id']}", specialist)
    if refreshed["is_outdated"] is not False or refreshed["installed_version"] != "1.0.1":
        raise SmokeError(refreshed)
    again = request(
        "POST",
        "/api/version-checks/run",
        specialist,
        {"client_configuration_id": installation["id"]},
        expected=201,
    )
    if again["created"][0]["is_outdated"] is not False:
        raise SmokeError(again)
    inbox = request("GET", "/api/notifications?" + urlencode({"type": "update_completed"}), portal_token)
    if inbox["total"] < 1:
        raise SmokeError(inbox)
    ok("4.4 status changes and installed version advanced")

    updated = request("GET", "/api/reports/updated-clients?" + urlencode({"q": company}), manager)
    if updated["total_clients"] != 1 or updated["clients"][0]["updates"][0]["target_version"] != "1.0.1":
        raise SmokeError(updated)
    demo_updated = request("GET", "/api/reports/updated-clients?" + urlencode({"q": "Василёк"}), manager)
    if demo_updated["total_updates"] < 1:
        raise SmokeError(demo_updated)
    ok("5.1 clients whose configurations were updated")

    summary = request("GET", "/api/reports/updates", manager)
    expected_planned = (
        summary["by_status"]["requested"]
        + summary["by_status"]["scheduled"]
        + summary["by_status"]["in_progress"]
    )
    if summary["planned_count"] != expected_planned or summary["completed_count"] < 1:
        raise SmokeError(summary)
    if not any(item["company_name"] == company for item in summary["completed"]):
        raise SmokeError(summary)
    head_outdated = request("GET", "/api/reports/outdated-clients?" + urlencode({"q": "Ромашка"}), manager)
    if head_outdated["total_clients"] < 1:
        raise SmokeError(head_outdated)
    gone = request("GET", "/api/reports/outdated-clients?" + urlencode({"q": company}), manager)
    if gone["total_clients"] != 0:
        raise SmokeError(gone)
    ok("5.2 completed vs planned, and the head's outdated list")

    request("DELETE", f"/api/clients/{blank['id']}", admin, expected=204)
    request("DELETE", f"/api/clients/{created_client['id']}", specialist, expected=409)
    ok("history blocks client delete; empty client can be removed")
    print(f"smoke passed against {BASE} at {datetime.now().isoformat(timespec='seconds')}")


if __name__ == "__main__":
    try:
        main()
    except SmokeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
