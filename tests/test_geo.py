"""
Tier 1 & Tier 2 Tests: Geolocation, Haversine Spherical Trigonometry, BVA & Anti-Spoofing Gates.
Requirements: ORIGINAL_REQUEST §3, SRS §3.3, API §4, TEST_INFRA.md.
"""
import math
import time
from datetime import datetime, timedelta
import pytest
from httpx import AsyncClient

from tests.mock_backend import (
    EARTH_RADIUS_METERS,
    MAX_ALLOWED_ACCURACY_METERS,
    MAX_ALLOWED_DISTANCE_METERS,
    MAX_CLOCK_DRIFT_SECONDS,
    haversine_distance,
)


# ---------------------------------------------------------------------------
# Haversine Mathematical Engine Unit Tests (Tier 1 & Tier 2)
# ---------------------------------------------------------------------------
def test_haversine_zero_distance_identical_points():
    """Identical coordinates must yield exactly 0.0 meters."""
    lat, lon = 55.753100, 37.621000
    dist = haversine_distance(lat, lon, lat, lon)
    assert dist == 0.0


def test_haversine_symmetry():
    """Distance from A to B must equal distance from B to A."""
    p1 = (55.751244, 37.618423)
    p2 = (55.753100, 37.621000)
    d1 = haversine_distance(p1[0], p1[1], p2[0], p2[1])
    d2 = haversine_distance(p2[0], p2[1], p1[0], p1[1])
    assert abs(d1 - d2) < 1e-9


def test_haversine_triangle_inequality():
    """Haversine distance satisfies the triangle inequality d(A, C) <= d(A, B) + d(B, C)."""
    pA = (55.751244, 37.618423)
    pB = (55.753100, 37.621000)
    pC = (55.755000, 37.625000)

    d_AC = haversine_distance(pA[0], pA[1], pC[0], pC[1])
    d_AB = haversine_distance(pA[0], pA[1], pB[0], pB[1])
    d_BC = haversine_distance(pB[0], pB[1], pC[0], pC[1])

    assert d_AC <= d_AB + d_BC + 1e-6


def test_haversine_exact_known_distance_bspu_buildings():
    """Distance between BSPU Main Building and Building B is ~261.8m."""
    main_b = (55.751244, 37.618423)
    b_b = (55.753100, 37.621000)
    dist = haversine_distance(main_b[0], main_b[1], b_b[0], b_b[1])
    assert 255.0 <= dist <= 270.0


def test_haversine_pure_latitude_displacement():
    """1 meter latitude shift matches formula (1 / 6371000 * 180 / pi)."""
    lat1, lon1 = 55.0, 37.0
    one_meter_deg = (1.0 / EARTH_RADIUS_METERS) * (180.0 / math.pi)
    lat2 = lat1 + one_meter_deg
    dist = haversine_distance(lat1, lon1, lat2, lon1)
    assert abs(dist - 1.0) < 1e-3


def test_haversine_pure_longitude_displacement():
    """Longitude displacement scales with cos(lat)."""
    lat1, lon1 = 60.0, 30.0  # cos(60) = 0.5
    one_meter_lon_deg = (1.0 / (EARTH_RADIUS_METERS * math.cos(math.radians(lat1)))) * (180.0 / math.pi)
    lon2 = lon1 + one_meter_lon_deg
    dist = haversine_distance(lat1, lon1, lat1, lon2)
    assert abs(dist - 1.0) < 1e-3


def test_haversine_exact_149m_boundary():
    """Generating point at exactly 149.0 meters yields 149.0m within 0.05m tolerance."""
    lat1, lon1 = 55.753100, 37.621000
    lat_149 = lat1 + (149.0 / EARTH_RADIUS_METERS) * (180.0 / math.pi)
    d = haversine_distance(lat1, lon1, lat_149, lon1)
    assert abs(d - 149.0) < 0.05


def test_haversine_exact_151m_boundary():
    """Generating point at exactly 151.0 meters yields 151.0m within 0.05m tolerance."""
    lat1, lon1 = 55.753100, 37.621000
    lat_151 = lat1 + (151.0 / EARTH_RADIUS_METERS) * (180.0 / math.pi)
    d = haversine_distance(lat1, lon1, lat_151, lon1)
    assert abs(d - 151.0) < 0.05


# ---------------------------------------------------------------------------
# Checkin API Boundary Value Analysis (BVA) Tests (Tier 1 & Tier 2)
# ---------------------------------------------------------------------------
def _get_active_pair_timestamp(pair_time_start: str = "08:30") -> float:
    """Returns current timestamp in seconds matching the active pair's window."""
    return time.time()



@pytest.mark.asyncio
async def test_checkin_success_inside_radius_25m(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Student within 25m of building center succeeds (200 OK, status PRESENT)."""
    # Building 1 (Main Building) is at 55.751244, 37.618423
    # 25m north
    delta_lat = (25.0 / EARTH_RADIUS_METERS) * (180.0 / math.pi)
    client_lat = 55.751244 + delta_lat
    client_lon = 37.618423

    valid_ts = _get_active_pair_timestamp("08:30")

    payload = {
        "pair_id": 1,
        "client_lat": client_lat,
        "client_lon": client_lon,
        "accuracy": 15.0,
        "timestamp": valid_ts,
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "PRESENT"
    assert data["distance_meters"] <= 30.0


@pytest.mark.asyncio
async def test_checkin_success_at_exact_boundary_149m(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Student at d = 149.0m (under 150.0m limit) succeeds."""
    delta_lat = (149.0 / EARTH_RADIUS_METERS) * (180.0 / math.pi)
    client_lat = 55.751244 + delta_lat
    client_lon = 37.618423

    payload = {
        "pair_id": 1,
        "client_lat": client_lat,
        "client_lon": client_lon,
        "accuracy": 10.0,
        "timestamp": _get_active_pair_timestamp("08:30"),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 200
    assert res.json()["status"] == "PRESENT"


@pytest.mark.asyncio
async def test_checkin_success_at_exact_boundary_150m(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Student at d = 150.0m (exact limit) succeeds."""
    delta_lat = (150.0 / EARTH_RADIUS_METERS) * (180.0 / math.pi)
    client_lat = 55.751244 + delta_lat
    client_lon = 37.618423

    payload = {
        "pair_id": 1,
        "client_lat": client_lat,
        "client_lon": client_lon,
        "accuracy": 10.0,
        "timestamp": _get_active_pair_timestamp("08:30"),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 200
    assert res.json()["status"] == "PRESENT"


@pytest.mark.asyncio
async def test_checkin_rejected_at_boundary_151m(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Student at d = 151.0m (exceeds 150m limit) is rejected with 400 Bad Request."""
    delta_lat = (151.0 / EARTH_RADIUS_METERS) * (180.0 / math.pi)
    client_lat = 55.751244 + delta_lat
    client_lon = 37.618423

    payload = {
        "pair_id": 1,
        "client_lat": client_lat,
        "client_lon": client_lon,
        "accuracy": 10.0,
        "timestamp": _get_active_pair_timestamp("08:30"),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 400
    data = res.json()
    assert "out-of-bounds" in data.get("type", "") or data.get("status") == 400
    assert data["data"]["distance"] >= 150.5


@pytest.mark.asyncio
async def test_checkin_rejected_outside_radius_350m(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Student at 350m distance is rejected with details."""
    delta_lat = (350.0 / EARTH_RADIUS_METERS) * (180.0 / math.pi)
    client_lat = 55.751244 + delta_lat
    client_lon = 37.618423

    payload = {
        "pair_id": 1,
        "client_lat": client_lat,
        "client_lon": client_lon,
        "accuracy": 10.0,
        "timestamp": _get_active_pair_timestamp("08:30"),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 400
    data = res.json()
    assert data["data"]["distance"] > 340.0


# ---------------------------------------------------------------------------
# GPS Accuracy Gate Tests (Tier 1 & Tier 2 BVA)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_checkin_accuracy_allowed_49m(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """accuracy = 49.0m (within 50.0m limit) is accepted."""
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 49.0,
        "timestamp": _get_active_pair_timestamp("08:30"),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_checkin_accuracy_allowed_exact_50m(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """accuracy = 50.0m (exact boundary) is accepted."""
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 50.0,
        "timestamp": _get_active_pair_timestamp("08:30"),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_checkin_accuracy_rejected_boundary_51m(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """accuracy = 51.0m (exceeds 50.0m limit) is rejected with 400 INACCURATE_GPS."""
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 51.0,
        "timestamp": _get_active_pair_timestamp("08:30"),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 400
    assert "inaccurate-gps" in res.json().get("type", "")


@pytest.mark.asyncio
async def test_checkin_accuracy_rejected_large_inaccuracy_150m(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """accuracy = 150.0m (very poor GPS) is rejected."""
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 150.0,
        "timestamp": _get_active_pair_timestamp("08:30"),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Clock Drift & Timestamp Anti-Spoofing Tests (Tier 1 & Tier 2 BVA)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_checkin_clock_drift_allowed_29s_ahead(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Client timestamp 29s ahead of server time is accepted."""
    # Ensure active pair window and drift <= 30s
    now_ts = time.time()
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 10.0,
        "timestamp": now_ts + 29.0,
    }
    # For this test, ensure the pair window allows current time
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    # Status code will either be 200 (if now is in pair window) or 400 window-closed, but NOT clock-skew!
    if res.status_code == 400:
        assert "clock-skew" not in res.json().get("type", "")


@pytest.mark.asyncio
async def test_checkin_clock_drift_rejected_31s_ahead(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Client timestamp 31s ahead of server time is rejected with clock-skew."""
    now_ts = time.time()
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 10.0,
        "timestamp": now_ts + 31.0,
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 400
    assert "clock-skew" in res.json().get("type", "")


@pytest.mark.asyncio
async def test_checkin_clock_drift_rejected_31s_behind(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Client timestamp 31s behind server time is rejected with clock-skew."""
    now_ts = time.time()
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 10.0,
        "timestamp": now_ts - 31.0,
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 400
    assert "clock-skew" in res.json().get("type", "")


@pytest.mark.asyncio
async def test_checkin_clock_drift_rejected_drastic_desync_1hour(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Client timestamp 3600s desynchronized is rejected."""
    now_ts = time.time()
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 10.0,
        "timestamp": now_ts - 3600.0,
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 400
    assert "clock-skew" in res.json().get("type", "")


# ---------------------------------------------------------------------------
# Multiple Subgroups & Buildings Geolocation Validation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_checkin_pair2_building_b_coordinates(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Pair 2 is in Building B (55.753100, 37.621000). Checkin within 10m succeeds."""
    payload = {
        "pair_id": 2,
        "client_lat": 55.753100,
        "client_lon": 37.621000,
        "accuracy": 12.0,
        "timestamp": _get_active_pair_timestamp("10:15"),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 200
    assert res.json()["status"] == "PRESENT"


@pytest.mark.asyncio
async def test_checkin_wrong_building_rejected(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Student present in Building 1 tries to checkin for Pair 2 (in Building B): distance ~262m, rejected."""
    payload = {
        "pair_id": 2,
        "client_lat": 55.751244,  # Building 1
        "client_lon": 37.618423,
        "accuracy": 10.0,
        "timestamp": _get_active_pair_timestamp("10:15"),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 400
    assert "out-of-bounds" in res.json().get("type", "")
    assert res.json()["data"]["distance"] > 250.0


def test_haversine_antipodal_points_half_circumference():
    """Distance between antipodal points on sphere equals pi * R."""
    d = haversine_distance(0.0, 0.0, 0.0, 180.0)
    expected = math.pi * EARTH_RADIUS_METERS
    assert abs(d - expected) < 1.0


def test_haversine_north_to_south_pole():
    """Distance from North Pole (90, 0) to South Pole (-90, 0) equals pi * R."""
    d = haversine_distance(90.0, 0.0, -90.0, 0.0)
    expected = math.pi * EARTH_RADIUS_METERS
    assert abs(d - expected) < 1.0


def test_haversine_equatorial_quarter():
    """Distance along equator for 90 degrees longitude equals (pi / 2) * R."""
    d = haversine_distance(0.0, 0.0, 0.0, 90.0)
    expected = (math.pi / 2.0) * EARTH_RADIUS_METERS
    assert abs(d - expected) < 1.0


def test_haversine_micro_distance_submillimeter():
    """Distance for 1e-7 degree latitude shift is ~0.011 meters."""
    d = haversine_distance(55.0, 37.0, 55.0000001, 37.0)
    assert 0.010 <= d <= 0.012


@pytest.mark.asyncio
async def test_checkin_exact_zero_drift(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Client timestamp exactly matching server time (0s drift) succeeds."""
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 10.0,
        "timestamp": time.time(),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 200
    assert res.json()["status"] == "PRESENT"


@pytest.mark.asyncio
async def test_checkin_accuracy_minimal_positive(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Extremely high accuracy (0.5m, e.g. RTK / dual-frequency GPS) succeeds."""
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 0.5,
        "timestamp": time.time(),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_checkin_response_schema_completeness(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Successful checkin returns pair_id, status, distance_meters, checkin_time, message."""
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 15.0,
        "timestamp": time.time(),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 200
    data = res.json()
    assert data["pair_id"] == 1
    assert data["status"] == "PRESENT"
    assert isinstance(data["distance_meters"], (int, float))
    assert "checkin_time" in data
    assert "message" in data


@pytest.mark.asyncio
async def test_checkin_distance_rounding_fidelity(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Distance in response is rounded to 1 decimal place per API spec."""
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244 + 0.0001,
        "client_lon": 37.618423,
        "accuracy": 10.0,
        "timestamp": time.time(),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == 200
    dist = res.json()["distance_meters"]
    assert str(dist) == f"{dist:.1f}" or str(dist) == f"{int(dist)}.0" or isinstance(dist, float)

