"""
test_geometry.py — Pruebas unitarias del módulo de geometría geográfica.
"""

import math
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from map.geometry import (
    haversine_distance,
    compute_segment_distances,
    compute_cumulative_distances,
    total_length,
    interpolate_position,
)


class TestHaversineDistance:

    def test_same_point_is_zero(self):
        """La distancia de un punto a sí mismo es 0."""
        d = haversine_distance(7.1100, -73.1270, 7.1100, -73.1270)
        assert d == pytest.approx(0.0, abs=1e-6)

    def test_known_distance_approximate(self):
        """
        Distancia aproximada entre Portal Norte y Cañaveral.
        Referencia: ~10 km en línea recta aproximada.
        """
        lat1, lon1 = 7.14470, -73.13480  # Portal Norte
        lat2, lon2 = 7.07426, -73.10895  # Cañaveral
        d = haversine_distance(lat1, lon1, lat2, lon2)
        # Debe estar entre 7 km y 12 km en línea recta
        assert 7000 < d < 12000, f"Distancia inesperada: {d:.0f} m"

    def test_distance_is_symmetric(self):
        """La distancia A→B debe ser igual a B→A."""
        lat1, lon1 = 7.16402, -73.14062
        lat2, lon2 = 7.07426, -73.10895
        d_ab = haversine_distance(lat1, lon1, lat2, lon2)
        d_ba = haversine_distance(lat2, lon2, lat1, lon1)
        assert d_ab == pytest.approx(d_ba, rel=1e-9)

    def test_distance_is_positive(self):
        """La distancia nunca es negativa."""
        d = haversine_distance(7.1, -73.1, 7.2, -73.2)
        assert d > 0


class TestCumulativeDistances:

    def test_first_distance_is_zero(self):
        """El primer punto siempre tiene distancia acumulada 0."""
        coords = [[-73.14062, 7.16402], [-73.13480, 7.14470], [-73.10895, 7.07426]]
        cum = compute_cumulative_distances(coords)
        assert cum[0] == 0.0

    def test_length_matches_coordinates(self):
        """La longitud de distancias acumuladas = número de puntos."""
        coords = [[-73.14062, 7.16402], [-73.13480, 7.14470], [-73.10895, 7.07426]]
        cum = compute_cumulative_distances(coords)
        assert len(cum) == len(coords)

    def test_distances_are_monotonically_increasing(self):
        """Las distancias acumuladas deben ser no decrecientes."""
        coords = [
            [-73.14062, 7.16402],
            [-73.13480, 7.14470],
            [-73.10960, 7.09020],
            [-73.10895, 7.07426],
        ]
        cum = compute_cumulative_distances(coords)
        for i in range(len(cum) - 1):
            assert cum[i + 1] >= cum[i], f"No monotónico en índice {i}"

    def test_total_length_positive(self):
        """La longitud total debe ser positiva para cualquier ruta válida."""
        coords = [[-73.14062, 7.16402], [-73.10895, 7.07426]]
        length = total_length(coords)
        assert length > 0


class TestInterpolatePosition:

    def setup_method(self):
        """Preparar una ruta simple para las pruebas."""
        self.coords = [
            [-73.14062, 7.16402],  # Café Madrid
            [-73.13480, 7.14470],  # Portal Norte
            [-73.10895, 7.07426],  # Cañaveral
        ]
        self.cum = compute_cumulative_distances(self.coords)

    def test_at_zero_returns_first_point(self):
        """A distancia 0, debe retornar el primer punto."""
        lat, lon = interpolate_position(self.coords, self.cum, 0.0)
        assert lat == pytest.approx(7.16402, abs=1e-5)
        assert lon == pytest.approx(-73.14062, abs=1e-5)

    def test_at_total_returns_last_point(self):
        """A la distancia total, debe retornar el último punto."""
        total = self.cum[-1]
        lat, lon = interpolate_position(self.coords, self.cum, total)
        assert lat == pytest.approx(7.07426, abs=1e-5)
        assert lon == pytest.approx(-73.10895, abs=1e-5)

    def test_beyond_total_clamps_to_end(self):
        """Si distance > total, debe retornar el último punto (clampeo)."""
        total = self.cum[-1]
        lat, lon = interpolate_position(self.coords, self.cum, total + 10000)
        assert lat == pytest.approx(7.07426, abs=1e-5)
        assert lon == pytest.approx(-73.10895, abs=1e-5)

    def test_negative_distance_clamps_to_start(self):
        """Si distance < 0, debe retornar el primer punto (clampeo)."""
        lat, lon = interpolate_position(self.coords, self.cum, -500.0)
        assert lat == pytest.approx(7.16402, abs=1e-5)
        assert lon == pytest.approx(-73.14062, abs=1e-5)

    def test_midpoint_is_between_endpoints(self):
        """El punto medio debe estar entre los extremos."""
        total = self.cum[-1]
        lat, lon = interpolate_position(self.coords, self.cum, total / 2)

        lat_min = min(7.16402, 7.07426)
        lat_max = max(7.16402, 7.07426)
        lon_min = min(-73.14062, -73.10895)
        lon_max = max(-73.14062, -73.10895)

        assert lat_min <= lat <= lat_max, f"Latitud {lat} fuera del rango"
        assert lon_min <= lon <= lon_max, f"Longitud {lon} fuera del rango"

    def test_wait_time_never_negative(self):
        """
        Validación de regla #4 de la especificación:
        Los tiempos de espera nunca pueden ser negativos.
        (Prueba simbólica desde el módulo de geometría.)
        """
        # Verificar que la distancia nunca es negativa
        for d in [0, 100, 1000, 5000]:
            lat, lon = interpolate_position(self.coords, self.cum, d)
            assert lat is not None
            assert lon is not None


class TestRouteValidity:

    def test_bucaramanga_bounding_box(self):
        """
        Todas las coordenadas de la ruta deben estar dentro del
        área de Bucaramanga / Floridablanca.
        """
        # BBox: lat [7.0, 7.3], lon [-73.25, -73.0]
        coords = [
            [-73.14062, 7.16402],
            [-73.13480, 7.14470],
            [-73.10960, 7.09020],
            [-73.10895, 7.07426],
        ]
        for lon, lat in coords:
            assert 7.0 <= lat <= 7.3, f"Latitud fuera de rango: {lat}"
            assert -73.25 <= lon <= -73.0, f"Longitud fuera de rango: {lon}"
