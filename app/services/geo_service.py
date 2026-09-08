"""
Сервис расчета дистанции и валидации геолокации студента.
"""
import math
from app.core.config import settings

EARTH_RADIUS_METERS = 6371000.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Вычисляет расстояние между двумя GPS координатами по формуле гаверсинусов (в метрах)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c


def validate_checkin_location(
    client_lat: float,
    client_lon: float,
    accuracy: float,
    target_lat: float,
    target_lon: float,
    max_radius: float = settings.MAX_ALLOWED_DISTANCE_METERS,
    max_accuracy: float = settings.MAX_GPS_ACCURACY_METERS,
) -> tuple[bool, float, str]:
    """
    Проверяет валидность геолокации.
    Возвращает (is_valid, distance, error_message).
    """
    if accuracy > max_accuracy:
        return False, 0.0, f"Низкая точность GPS ({accuracy:.1f} м). Требуется <= {max_accuracy:.1f} м."

    distance = haversine_distance(client_lat, client_lon, target_lat, target_lon)
    if distance > max_radius:
        return False, distance, f"Вы находитесь вне аудиторного фонда (дистанция: {distance:.1f} м при лимите {max_radius:.1f} м)."

    return True, distance, ""
