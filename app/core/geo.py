"""
Spherical Haversine distance engine and GPS anti-spoofing verification for attendance check-in.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Optional, Tuple


# Mean spherical radius of the Earth specified in SRS §5.1
EARTH_RADIUS_METERS: float = 6371000.0

# Operational thresholds
DEFAULT_MAX_DISTANCE_METERS: float = 150.0
DEFAULT_MAX_ACCURACY_METERS: float = 50.0
DEFAULT_MAX_TIMESTAMP_SKEW_SECONDS: float = 30.0


@dataclass(frozen=True)
class GeoVerificationResult:
    """Structured outcome of a geolocation attendance verification check."""
    is_valid: bool
    distance_meters: float
    accuracy_meters: float
    max_allowed_distance: float
    error_code: Optional[str] = None
    error_detail: Optional[str] = None


def haversine_distance(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Calculate great-circle distance between two GPS coordinates in meters.
    Calibrated to R = 6,371,000 meters.
    """
    # Sanity bounds check
    if not (-90.0 <= lat1 <= 90.0 and -90.0 <= lat2 <= 90.0):
        raise ValueError(f"Latitude out of bounds [-90, 90]: lat1={lat1}, lat2={lat2}")
    if not (-180.0 <= lon1 <= 180.0 and -180.0 <= lon2 <= 180.0):
        raise ValueError(f"Longitude out of bounds [-180, 180]: lon1={lon1}, lon2={lon2}")

    # Identical coordinates short-circuit
    if lat1 == lat2 and lon1 == lon2:
        return 0.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )

    # Numerical stability clamping
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_METERS * c


def validate_gps_accuracy(
    accuracy: float,
    max_accuracy: float = DEFAULT_MAX_ACCURACY_METERS,
) -> Tuple[bool, Optional[str]]:
    """
    Validate that mobile device GPS sensor precision meets threshold (accuracy <= 50.0m).
    """
    if accuracy <= 0.0:
        return False, "INVALID_GPS_ACCURACY"
    if accuracy > max_accuracy:
        return False, "INACCURATE_GPS"
    return True, None


def validate_sensor_timestamp(
    client_timestamp: float | int,
    server_timestamp: Optional[float | int] = None,
    max_skew_seconds: float = DEFAULT_MAX_TIMESTAMP_SKEW_SECONDS,
) -> Tuple[bool, Optional[str]]:
    """
    Anti-spoofing clock skew guard: ensures GPS sample was generated recently (|drift| <= 30.0s).
    """
    now = server_timestamp if server_timestamp is not None else time.time()
    diff = abs(now - client_timestamp)
    if diff > max_skew_seconds:
        return False, "GPS_TIMESTAMP_SKEW"
    return True, None


def verify_geocheckin(
    client_lat: float,
    client_lon: float,
    accuracy: float,
    client_timestamp: float | int,
    building_lat: float,
    building_lon: float,
    max_radius: float = DEFAULT_MAX_DISTANCE_METERS,
    max_accuracy: float = DEFAULT_MAX_ACCURACY_METERS,
    max_skew_seconds: float = DEFAULT_MAX_TIMESTAMP_SKEW_SECONDS,
    server_timestamp: Optional[float | int] = None,
) -> GeoVerificationResult:
    """
    Comprehensive verification combining sensor accuracy, timestamp skew, and Haversine distance.
    """
    # 1. Check GPS accuracy
    acc_valid, acc_err = validate_gps_accuracy(accuracy, max_accuracy)
    if not acc_valid:
        return GeoVerificationResult(
            is_valid=False,
            distance_meters=-1.0,
            accuracy_meters=accuracy,
            max_allowed_distance=max_radius,
            error_code=acc_err,
            error_detail=f"Точность GPS ({accuracy:.1f} м) превышает допустимый порог ({max_accuracy:.1f} м). Пожалуйста, выйдите к окну.",
        )

    # 2. Check timestamp drift
    time_valid, time_err = validate_sensor_timestamp(client_timestamp, server_timestamp, max_skew_seconds)
    if not time_valid:
        return GeoVerificationResult(
            is_valid=False,
            distance_meters=-1.0,
            accuracy_meters=accuracy,
            max_allowed_distance=max_radius,
            error_code=time_err,
            error_detail="Временная метка координат не совпадает с серверным временем (> 30 сек). Проверьте системные часы устройства.",
        )

    # 3. Calculate distance
    dist = haversine_distance(client_lat, client_lon, building_lat, building_lon)

    if dist > max_radius:
        return GeoVerificationResult(
            is_valid=False,
            distance_meters=dist,
            accuracy_meters=accuracy,
            max_allowed_distance=max_radius,
            error_code="OUT_OF_BOUNDS",
            error_detail=f"Вы находитесь на расстоянии {dist:.1f} м от корпуса при максимально допустимом лимите {max_radius:.1f} м.",
        )

    return GeoVerificationResult(
        is_valid=True,
        distance_meters=dist,
        accuracy_meters=accuracy,
        max_allowed_distance=max_radius,
        error_code=None,
        error_detail=None,
    )
