import math
import time

METERS_PER_DEGREE_LAT = 111139.0
EARTH_RADIUS_METERS = 6371000.0


def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes exact great-circle distance between two points on the Earth
    using the Haversine formula (in meters).
    """
    for val in (lat1, lon1, lat2, lon2):
        if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
            return 9999999.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c


def fast_geocheck(
    client_lat: float, client_lon: float, target_lat: float, target_lon: float, radius_meters: float = 150.0
) -> tuple[bool, float]:
    """
    Ultra-fast two-phase Geofencing:
    Phase 1: Bounding Box check (O(1), 0.002ms) to reject distant points.
    Phase 2: Exact Haversine calculation for points inside or near the bounding box.
    Returns: (is_within_radius, distance_in_meters)
    """
    for val in (client_lat, client_lon, target_lat, target_lon, radius_meters):
        if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
            return False, 9999999.0

    # Phase 1: Fast Bounding Box
    lat_deg_delta = radius_meters / METERS_PER_DEGREE_LAT
    avg_lat = (client_lat + target_lat) / 2.0
    cos_lat = max(math.cos(math.radians(avg_lat)), 0.001)
    lon_deg_delta = radius_meters / (METERS_PER_DEGREE_LAT * cos_lat)

    if abs(client_lat - target_lat) > lat_deg_delta or abs(client_lon - target_lon) > lon_deg_delta:
        # Far away - calculate exact distance only for error reporting
        distance = calculate_haversine_distance(client_lat, client_lon, target_lat, target_lon)
        return False, round(distance, 1)

    # Phase 2: Exact Haversine
    distance = calculate_haversine_distance(client_lat, client_lon, target_lat, target_lon)
    return distance <= radius_meters, round(distance, 1)


def validate_coordinates_accuracy(accuracy: float | None, max_accuracy: float = 50.0) -> tuple[bool, str | None]:
    """Validates GPS accuracy against threshold (default <= 50m)."""
    if (
        accuracy is None
        or not isinstance(accuracy, (int, float))
        or math.isnan(accuracy)
        or math.isinf(accuracy)
        or accuracy <= 0
    ):
        return False, "Не удалось определить точность GPS. Включите геолокацию на устройстве."
    if accuracy > max_accuracy:
        return (
            False,
            f"Точность GPS ({accuracy:.1f} м) ниже допустимой (максимум {max_accuracy:.0f} м). Выйдите ближе к окну.",
        )
    return True, None


def validate_client_timestamp(
    client_timestamp: float | None, max_drift_seconds: float = 60.0
) -> tuple[bool, str | None]:
    """Anti-spoofing: checks time drift between device and server."""
    if client_timestamp is None:
        return True, None  # Optional

    if (
        not isinstance(client_timestamp, (int, float))
        or math.isnan(client_timestamp)
        or math.isinf(client_timestamp)
        or client_timestamp <= 0
    ):
        return False, "Некорректная временная метка устройства."

    # Support both seconds and milliseconds timestamp
    if client_timestamp > 1e11:
        client_timestamp = client_timestamp / 1000.0

    current_server_time = time.time()
    drift = abs(current_server_time - client_timestamp)
    if drift > max_drift_seconds:
        return (
            False,
            f"Рассинхронизация часов устройства и сервера ({drift:.0f} сек). Проверьте дату и время на смартфоне.",
        )
    return True, None
