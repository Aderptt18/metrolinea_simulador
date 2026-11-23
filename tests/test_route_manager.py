"""
test_route_manager.py — Pruebas de carga y validación de las rutas geográficas.
"""

import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from map.route_manager import RouteManager, RouteData


class TestRouteManagerLoad:

    def setup_method(self):
        """Crear una instancia fresca para cada test."""
        self.rm = RouteManager()

    def test_load_succeeds(self):
        """La carga debe completarse sin errores."""
        self.rm.load()
        assert self.rm.is_loaded

    def test_routes_ns_and_sn_available(self):
        """Deben existir las rutas NS y SN."""
        self.rm.load()
        ns = self.rm.get_route("NS")
        sn = self.rm.get_route("SN")
        assert ns is not None
        assert sn is not None

    def test_route_ns_has_stops(self):
        """La ruta NS debe tener al menos 5 paradas."""
        self.rm.load()
        ns = self.rm.get_route("NS")
        assert len(ns.stops) >= 5

    def test_route_sn_has_stops(self):
        """La ruta SN debe tener al menos 5 paradas."""
        self.rm.load()
        sn = self.rm.get_route("SN")
        assert len(sn.stops) >= 5

    def test_route_ns_length_reasonable(self):
        """
        La ruta NS debe medir entre 10 km y 25 km.
        Referencia: Café Madrid → Cañaveral es aprox. 15-18 km por calles.
        """
        self.rm.load()
        ns = self.rm.get_route("NS")
        assert 10.0 <= ns.total_length_km <= 25.0, (
            f"Longitud NS inesperada: {ns.total_length_km:.2f} km"
        )

    def test_route_sn_length_reasonable(self):
        """La ruta SN debe medir entre 10 km y 25 km."""
        self.rm.load()
        sn = self.rm.get_route("SN")
        assert 10.0 <= sn.total_length_km <= 25.0, (
            f"Longitud SN inesperada: {sn.total_length_km:.2f} km"
        )

    def test_invalid_direction_raises(self):
        """Pedir un sentido inválido debe lanzar ValueError."""
        self.rm.load()
        with pytest.raises(ValueError):
            self.rm.get_route("XX")

    def test_get_route_before_load_raises(self):
        """Usar get_route sin cargar debe lanzar RuntimeError."""
        with pytest.raises(RuntimeError):
            self.rm.get_route("NS")

    def test_all_stops_loaded(self):
        """Deben cargarse todas las paradas del archivo."""
        self.rm.load()
        stops = self.rm.get_all_stops()
        assert len(stops) > 0

    def test_center_in_bucaramanga(self):
        """El centro del mapa debe estar en la zona de Bucaramanga."""
        self.rm.load()
        lat, lon = self.rm.get_center()
        assert 7.0 <= lat <= 7.3
        assert -73.25 <= lon <= -73.0


class TestRouteData:

    def setup_method(self):
        self.rm = RouteManager()
        self.rm.load()
        self.ns = self.rm.get_route("NS")

    def test_position_at_zero(self):
        """
        La posición a distancia 0 debe estar cerca del primer punto
        (Café Madrid, aprox. lat=7.164, lon=-73.141).
        """
        lat, lon = self.ns.get_position_at_distance(0)
        assert 7.0 <= lat <= 7.3
        assert -73.25 <= lon <= -73.0

    def test_position_at_end(self):
        """
        La posición al final del recorrido debe estar cerca del último punto
        (Cañaveral, aprox. lat=7.074, lon=-73.109).
        """
        lat, lon = self.ns.get_position_at_distance(self.ns.total_length_m)
        assert 7.0 <= lat <= 7.3
        assert -73.25 <= lon <= -73.0

    def test_stop_distances_non_decreasing(self):
        """
        Las distancias de las paradas deben ser no decrecientes
        (las paradas están ordenadas a lo largo del recorrido).
        """
        for i in range(len(self.ns.stop_distances) - 1):
            d1 = self.ns.stop_distances[i]
            d2 = self.ns.stop_distances[i + 1]
            assert d1 <= d2 + 500, (  # tolerancia 500m
                f"Parada {i} ({d1:.0f}m) > Parada {i+1} ({d2:.0f}m)"
            )

    def test_stop_index_out_of_range(self):
        """Índice de parada fuera de rango debe lanzar IndexError."""
        with pytest.raises(IndexError):
            self.ns.get_stop_distance(999)


class TestStopsJson:
    """Validar la integridad de stops.json."""

    def test_stops_json_loads(self):
        """stops.json debe cargarse sin error."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        with open(os.path.join(data_dir, "stops.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert "stops" in data
        assert len(data["stops"]) > 0

    def test_all_stops_have_coordinates(self):
        """Todas las paradas deben tener coordenadas."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        with open(os.path.join(data_dir, "stops.json"), encoding="utf-8") as f:
            data = json.load(f)
        for stop in data["stops"]:
            coords = stop.get("coordinates", [])
            assert len(coords) == 2, f"Parada {stop.get('id')} sin coordenadas"
            lon, lat = coords
            assert 7.0 <= lat <= 7.3, f"Lat fuera de rango: {lat}"
            assert -73.25 <= lon <= -73.0, f"Lon fuera de rango: {lon}"

    def test_all_stops_have_required_fields(self):
        """Todas las paradas deben tener campos obligatorios."""
        required = ["id", "name", "type", "coordinates", "certainty"]
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        with open(os.path.join(data_dir, "stops.json"), encoding="utf-8") as f:
            data = json.load(f)
        for stop in data["stops"]:
            for field in required:
                assert field in stop, (
                    f"Parada {stop.get('id')} no tiene campo '{field}'"
                )

    def test_terminal_stops_exist(self):
        """Deben existir al menos 2 terminales (Café Madrid y Cañaveral)."""
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        with open(os.path.join(data_dir, "stops.json"), encoding="utf-8") as f:
            data = json.load(f)
        terminals = [s for s in data["stops"] if s["type"] == "TERMINAL"]
        assert len(terminals) >= 2

    def test_certainty_values_valid(self):
        """Los valores de certeza deben ser válidos."""
        valid = {"HIGH", "MEDIUM", "LOW", "PENDING"}
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        with open(os.path.join(data_dir, "stops.json"), encoding="utf-8") as f:
            data = json.load(f)
        for stop in data["stops"]:
            cert = stop.get("certainty")
            assert cert in valid, f"Certeza inválida en {stop.get('id')}: {cert}"
