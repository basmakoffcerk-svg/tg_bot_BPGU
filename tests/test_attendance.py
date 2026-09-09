import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models import AttendanceStatusEnum
from services.attendance_service import (
    get_pair_grid,
    lock_pair,
    override_attendance_status,
    process_checkin,
)


@pytest.mark.asyncio
async def test_process_checkin_within_bounds(db_session: AsyncSession, seed_test_data):
    student = seed_test_data["student1"]
    pair = seed_test_data["pair"]
    slot = seed_test_data["slot"]

    # Client is 30m away from BSPU main building
    client_lat = slot.building_lat + 0.0002
    client_lon = slot.building_lon + 0.0002

    # Mock slot time to match current time
    now_dt = datetime.datetime.now()
    slot.time_start = f"{now_dt.hour:02d}:{now_dt.minute:02d}"
    await db_session.commit()

    success, msg, data = await process_checkin(
        session=db_session,
        student=student,
        pair_id=pair.id,
        client_lat=client_lat,
        client_lon=client_lon,
        accuracy=15.0,
    )

    assert success is True
    assert data["status"] == "PRESENT"
    assert data["distance_meters"] <= 150.0


@pytest.mark.asyncio
async def test_process_checkin_out_of_bounds(db_session: AsyncSession, seed_test_data):
    student = seed_test_data["student1"]
    pair = seed_test_data["pair"]
    slot = seed_test_data["slot"]

    # Client is 800m away
    client_lat = slot.building_lat + 0.008
    client_lon = slot.building_lon + 0.008

    now_dt = datetime.datetime.now()
    slot.time_start = f"{now_dt.hour:02d}:{now_dt.minute:02d}"
    await db_session.commit()

    success, msg, data = await process_checkin(
        session=db_session,
        student=student,
        pair_id=pair.id,
        client_lat=client_lat,
        client_lon=client_lon,
        accuracy=15.0,
    )

    assert success is False
    assert data.get("code") == "OUT_OF_BOUNDS"
    assert data.get("distance") > 150.0


@pytest.mark.asyncio
async def test_starosta_live_grid_and_override(db_session: AsyncSession, seed_test_data):
    starosta = seed_test_data["starosta"]
    pair = seed_test_data["pair"]
    student = seed_test_data["student1"]

    # Initial grid
    grid = await get_pair_grid(db_session, pair.id)
    assert grid is not None
    assert grid["pair_id"] == pair.id
    assert grid["summary"]["total_students"] >= 4

    # Starosta overrides student1 to ABSENT_EXCUSED with doctor note
    ok, msg, res = await override_attendance_status(
        session=db_session,
        admin_student=starosta,
        pair_id=pair.id,
        target_student_id=student.id,
        new_status=AttendanceStatusEnum.ABSENT_EXCUSED.value,
        excuse_reason="Справка №104 из поликлиники",
    )

    assert ok is True
    assert res["status"] == AttendanceStatusEnum.ABSENT_EXCUSED.value

    # Check grid reflects change
    updated_grid = await get_pair_grid(db_session, pair.id)
    assert updated_grid["summary"]["absent_excused_count"] == 1


@pytest.mark.asyncio
async def test_pair_locking_prevents_checkin(db_session: AsyncSession, seed_test_data):
    starosta = seed_test_data["starosta"]
    student = seed_test_data["student1"]
    pair = seed_test_data["pair"]
    slot = seed_test_data["slot"]

    # Lock pair
    lock_ok, lock_msg, lock_data = await lock_pair(db_session, starosta, pair.id)
    assert lock_ok is True
    assert lock_data["is_locked"] is True

    # Attempt checkin should fail
    success, msg, data = await process_checkin(
        session=db_session,
        student=student,
        pair_id=pair.id,
        client_lat=slot.building_lat,
        client_lon=slot.building_lon,
        accuracy=10.0,
    )

    assert success is False
    assert data.get("code") == "PAIR_LOCKED"
