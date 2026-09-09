import time

import pytest

from services.geo_service import (
    calculate_haversine_distance,
    fast_geocheck,
    validate_client_timestamp,
    validate_coordinates_accuracy,
)

# BSPU Building 2 (Minsk): 53.893769, 27.544440
BSPU_MAIN_LAT = 53.893769
BSPU_MAIN_LON = 27.544440


def test_haversine_same_point():
    d = calculate_haversine_distance(BSPU_MAIN_LAT, BSPU_MAIN_LON, BSPU_MAIN_LAT, BSPU_MAIN_LON)
    assert d == pytest.approx(0.0, abs=0.1)


def test_haversine_known_distance():
    # Point ~100m north (0.0009 degrees latitude)
    point_north_lat = BSPU_MAIN_LAT + 0.0009
    d = calculate_haversine_distance(BSPU_MAIN_LAT, BSPU_MAIN_LON, point_north_lat, BSPU_MAIN_LON)
    assert 95.0 <= d <= 105.0


def test_fast_geocheck_within_radius():
    # Point 40m away
    client_lat = BSPU_MAIN_LAT + 0.00035
    client_lon = BSPU_MAIN_LON + 0.00020
    is_ok, dist = fast_geocheck(client_lat, client_lon, BSPU_MAIN_LAT, BSPU_MAIN_LON, radius_meters=150.0)
    assert is_ok is True
    assert dist <= 150.0


def test_fast_geocheck_outside_radius():
    # Point ~500m away
    client_lat = BSPU_MAIN_LAT + 0.0045
    client_lon = BSPU_MAIN_LON + 0.0045
    is_ok, dist = fast_geocheck(client_lat, client_lon, BSPU_MAIN_LAT, BSPU_MAIN_LON, radius_meters=150.0)
    assert is_ok is False
    assert dist > 150.0


def test_accuracy_validation():
    ok, err = validate_coordinates_accuracy(20.0, max_accuracy=50.0)
    assert ok is True
    assert err is None

    ok_bad, err_bad = validate_coordinates_accuracy(75.5, max_accuracy=50.0)
    assert ok_bad is False
    assert "Точность GPS" in err_bad

    ok_none, err_none = validate_coordinates_accuracy(None)
    assert ok_none is False


def test_timestamp_drift_validation():
    now = time.time()
    ok, err = validate_client_timestamp(now, max_drift_seconds=30.0)
    assert ok is True

    # 2 minutes drift
    ok_drift, err_drift = validate_client_timestamp(now - 120.0, max_drift_seconds=30.0)
    assert ok_drift is False
    assert "Рассинхронизация" in err_drift
