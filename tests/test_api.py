import datetime

import pytest
from httpx import AsyncClient

from core.config import settings
from core.security import generate_test_init_data


@pytest.mark.asyncio
async def test_api_health(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert "database" in data


@pytest.mark.asyncio
async def test_api_auth_unauthorized(client: AsyncClient):
    # No header
    res = await client.post("/api/v1/auth/telegram")
    assert res.status_code == 401

    # Bad header
    res_bad = await client.post("/api/v1/auth/telegram", headers={"X-Telegram-Init-Data": "bad_data"})
    assert res_bad.status_code == 401


@pytest.mark.asyncio
async def test_api_auth_valid(client: AsyncClient, seed_test_data):
    init_data = generate_test_init_data(111111, settings.BOT_TOKEN, first_name="Иван", last_name="Иванов")
    res = await client.post("/api/v1/auth/telegram", headers={"X-Telegram-Init-Data": init_data})
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["full_name"] == "Иванов Иван Иванович"
    assert data["user"]["role"] == "STAROSTA"
    assert data["permissions"]["can_view_grid"] is True


@pytest.mark.asyncio
async def test_api_get_schedule(client: AsyncClient, seed_test_data, auth_headers_student):
    res = await client.get("/api/v1/schedule/today", headers=auth_headers_student)
    assert res.status_code == 200
    data = res.json()
    assert "pairs" in data
    assert len(data["pairs"]) >= 1


@pytest.mark.asyncio
async def test_api_grid_rbac_forbidden_for_student(client: AsyncClient, seed_test_data, auth_headers_student):
    # Ordinary student attempting to access Starosta grid
    pair = seed_test_data["pair"]
    res = await client.get(f"/api/v1/attendance/grid/{pair.id}", headers=auth_headers_student)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_api_grid_allowed_for_starosta(client: AsyncClient, seed_test_data, auth_headers_starosta):
    pair = seed_test_data["pair"]
    res = await client.get(f"/api/v1/attendance/grid/{pair.id}", headers=auth_headers_starosta)
    assert res.status_code == 200
    data = res.json()
    assert data["pair_id"] == pair.id
    assert "summary" in data
    assert "students" in data


@pytest.mark.asyncio
async def test_api_export_report(client: AsyncClient, seed_test_data, auth_headers_starosta):
    today = datetime.date.today()
    payload = {
        "date_from": (today - datetime.timedelta(days=7)).isoformat(),
        "date_to": today.isoformat(),
        "delivery_method": "DIRECT_DOWNLOAD",
    }
    res = await client.post("/api/v1/reports/export", json=payload, headers=auth_headers_starosta)
    assert res.status_code == 200
    data = res.json()
    assert "file_name" in data
    assert data["file_name"].endswith(".xlsx")


@pytest.mark.asyncio
async def test_api_checkin_success(client: AsyncClient, seed_test_data, auth_headers_student, db_session):
    slot = seed_test_data["slot"]
    pair = seed_test_data["pair"]

    # Match time window to current time
    now_dt = datetime.datetime.now()
    slot.time_start = f"{now_dt.hour:02d}:{now_dt.minute:02d}"
    await db_session.commit()

    payload = {
        "pair_id": pair.id,
        "client_lat": slot.building_lat + 0.0001,
        "client_lon": slot.building_lon + 0.0001,
        "accuracy": 12.0,
    }
    res = await client.post("/api/v1/attendance/checkin", json=payload, headers=auth_headers_student)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "PRESENT"
    assert data["distance_meters"] <= 150.0


@pytest.mark.asyncio
async def test_api_override_status(client: AsyncClient, seed_test_data, auth_headers_starosta):
    pair = seed_test_data["pair"]
    student = seed_test_data["student1"]

    payload = {
        "pair_id": pair.id,
        "student_id": student.id,
        "new_status": "MANUAL_CONFIRM",
        "excuse_reason": "Разрядился телефон",
    }
    res = await client.patch("/api/v1/attendance/override", json=payload, headers=auth_headers_starosta)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == "MANUAL_CONFIRM"


@pytest.mark.asyncio
async def test_api_lock_pair(client: AsyncClient, seed_test_data, auth_headers_starosta):
    pair = seed_test_data["pair"]
    res = await client.post(f"/api/v1/attendance/lock/{pair.id}", headers=auth_headers_starosta)
    assert res.status_code == 200
    data = res.json()
    assert data["is_locked"] is True


@pytest.mark.asyncio
async def test_api_broadcast_alert(client: AsyncClient, seed_test_data, auth_headers_starosta):
    payload = {"type": "INFO", "title": "Перенос лекции", "body": "Лекция по высшей математике состоится в ауд. 308."}
    res = await client.post("/api/v1/alerts/broadcast", json=payload, headers=auth_headers_starosta)
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "SENT"


@pytest.mark.asyncio
async def test_api_report_download_stream(client: AsyncClient, seed_test_data, auth_headers_starosta):
    today = datetime.date.today()
    from_date = (today - datetime.timedelta(days=7)).isoformat()
    to_date = today.isoformat()
    res = await client.get(
        f"/api/v1/reports/download?date_from={from_date}&date_to={to_date}", headers=auth_headers_starosta
    )
    assert res.status_code == 200
    assert "spreadsheetml" in res.headers["content-type"]
