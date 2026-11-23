"""
geometry.py — Funciones de geometría geográfica para el simulador.

Implementa interpolación de posición sobre LineString geográfico
usando la fórmula de Haversine para cálculo de distancias en la Tierra.

Todas las coordenadas se manejan en WGS84 (latitud, longitud).
"""

import math
from typing import Sequence, Tuple, List


# Radio medio de la Tierra (metros)
EARTH_RADIUS_M = 6_371_000.0


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calcula la distancia en metros entre dos puntos geográficos
    usando la fórmula de Haversine.

    Args:
        lat1, lon1: Coordenadas del punto 1 en grados decimales (WGS84)
        lat2, lon2: Coordenadas del punto 2 en grados decimales (WGS84)

    Returns:
        Distancia en metros (float)
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def compute_segment_distances(coordinates: List[List[float]]) -> List[float]:
    """
    Calcula las distancias en metros de cada segmento de un LineString.

    Args:
        coordinates: Lista de coordenadas [[lon, lat], [lon, lat], ...]
                     (formato GeoJSON: longitud primero)

    Returns:
        Lista de distancias en metros para cada segmento.
        Longitud = len(coordinates) - 1
    """
    distances = []
    for i in range(len(coordinates) - 1):
        lon1, lat1 = coordinates[i]
        lon2, lat2 = coordinates[i + 1]
        d = haversine_distance(lat1, lon1, lat2, lon2)
        distances.append(d)
    return distances


def compute_cumulative_distances(coordinates: List[List[float]]) -> List[float]:
    """
    Calcula las distancias acumuladas desde el origen a cada punto del LineString.

    Args:
        coordinates: Lista de coordenadas [[lon, lat], ...] en formato GeoJSON

    Returns:
        Lista de distancias acumuladas en metros.
        El primer valor es siempre 0.0.
        Longitud = len(coordinates)
    """
    cumulative = [0.0]
    for i in range(len(coordinates) - 1):
        lon1, lat1 = coordinates[i]
        lon2, lat2 = coordinates[i + 1]
        d = haversine_distance(lat1, lon1, lat2, lon2)
        cumulative.append(cumulative[-1] + d)
    return cumulative


def total_length(coordinates: List[List[float]]) -> float:
    """
    Calcula la longitud total del LineString en metros.

    Args:
        coordinates: Lista de coordenadas [[lon, lat], ...]

    Returns:
        Distancia total en metros
    """
    distances = compute_segment_distances(coordinates)
    return sum(distances)


def interpolate_position(
    coordinates: List[List[float]],
    cumulative_distances: List[float],
    distance_m: float,
) -> Tuple[float, float]:
    """
    Interpola la posición geográfica de un punto a una distancia dada
    sobre el LineString, usando interpolación lineal entre segmentos.

    Args:
        coordinates: Lista de coordenadas [[lon, lat], ...]
        cumulative_distances: Distancias acumuladas desde el origen (metros).
                              Debe calcularse con compute_cumulative_distances().
        distance_m: Distancia recorrida desde el origen (metros).
                    Se clampea automáticamente al rango [0, total_length].

    Returns:
        Tupla (latitud, longitud) de la posición interpolada en WGS84.
    """
    total = cumulative_distances[-1]

    # Clampear al rango válido
    distance_m = max(0.0, min(distance_m, total))

    # Encontrar el segmento donde cae la distancia
    for i in range(len(cumulative_distances) - 1):
        d_start = cumulative_distances[i]
        d_end = cumulative_distances[i + 1]

        if d_start <= distance_m <= d_end:
            segment_length = d_end - d_start

            if segment_length < 1e-9:
                # Segmento degenerado: retornar el punto de inicio
                lon, lat = coordinates[i]
                return lat, lon

            # Fracción dentro del segmento
            t = (distance_m - d_start) / segment_length

            lon1, lat1 = coordinates[i]
            lon2, lat2 = coordinates[i + 1]

            # Interpolación lineal (válida para distancias cortas en geografía)
            lat = lat1 + t * (lat2 - lat1)
            lon = lon1 + t * (lon2 - lon1)
            return lat, lon

    # Si llegamos aquí, retornar el último punto
    lon, lat = coordinates[-1]
    return lat, lon


def find_nearest_stop_index(
    coordinates: List[List[float]],
    cumulative_distances: List[float],
    stop_coordinates: List[List[float]],
) -> List[int]:
    """
    Para cada parada, encuentra el índice del punto del LineString más cercano
    y calcula la distancia acumulada en ese punto.

    Esto permite saber cuándo un bus "llega" a cada parada durante su recorrido.

    Args:
        coordinates: Coordenadas del LineString [[lon, lat], ...]
        cumulative_distances: Distancias acumuladas del LineString
        stop_coordinates: Coordenadas de las paradas [[lon, lat], ...]

    Returns:
        Lista de distancias acumuladas (metros) donde está cada parada.
        Longitud = len(stop_coordinates)
    """
    stop_distances = []

    for stop_lon, stop_lat in stop_coordinates:
        min_dist = float('inf')
        best_cumulative = 0.0

        for i in range(len(coordinates) - 1):
            lon1, lat1 = coordinates[i]
            lon2, lat2 = coordinates[i + 1]

            # Proyectar la parada sobre el segmento
            proj_dist = _project_point_on_segment(
                stop_lat, stop_lon,
                lat1, lon1,
                lat2, lon2
            )

            # Distancia de la parada al segmento proyectado
            proj_lat, proj_lon = _interpolate_on_segment(lat1, lon1, lat2, lon2, proj_dist)
            d = haversine_distance(stop_lat, stop_lon, proj_lat, proj_lon)

            if d < min_dist:
                min_dist = d
                segment_length = haversine_distance(lat1, lon1, lat2, lon2)
                best_cumulative = cumulative_distances[i] + proj_dist * segment_length

        stop_distances.append(best_cumulative)

    return stop_distances


def _project_point_on_segment(
    p_lat: float, p_lon: float,
    a_lat: float, a_lon: float,
    b_lat: float, b_lon: float,
) -> float:
    """
    Calcula la fracción t (0..1) de la proyección del punto P
    sobre el segmento A→B, en coordenadas aproximadas.

    Returns:
        Fracción t ∈ [0, 1] donde t=0 es A y t=1 es B.
    """
    ax = b_lon - a_lon
    ay = b_lat - a_lat
    bx = p_lon - a_lon
    by = p_lat - a_lat

    dot = ax * bx + ay * by
    len_sq = ax * ax + ay * ay

    if len_sq < 1e-18:
        return 0.0

    t = dot / len_sq
    return max(0.0, min(1.0, t))


def _interpolate_on_segment(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
    t: float,
) -> Tuple[float, float]:
    """Interpolación lineal sobre un segmento geográfico."""
    lat = lat1 + t * (lat2 - lat1)
    lon = lon1 + t * (lon2 - lon1)
    return lat, lon
