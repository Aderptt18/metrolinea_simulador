"""
route_manager.py — Gestión y validación de las rutas geográficas de la P19.

Carga los archivos GeoJSON, valida su estructura y proporciona
los datos geográficos procesados al resto de la aplicación.
"""

import json
import os
import logging
from typing import Dict, List, Optional, Tuple

from map.geometry import (
    compute_cumulative_distances,
    total_length,
    interpolate_position,
    find_nearest_stop_index,
)

logger = logging.getLogger(__name__)

# Rutas relativas a la raíz del proyecto
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_BASE_DIR, "data")

GEOJSON_NORTH_SOUTH = os.path.join(_DATA_DIR, "route_p19_north_south.geojson")
GEOJSON_SOUTH_NORTH = os.path.join(_DATA_DIR, "route_p19_south_north.geojson")
STOPS_FILE = os.path.join(_DATA_DIR, "stops.json")


class RouteData:
    """
    Contiene la geometría procesada de un sentido de la ruta P19.
    """

    def __init__(
        self,
        direction: str,
        coordinates: List[List[float]],
        stops: List[Dict],
        cumulative_distances: List[float],
        stop_distances: List[float],
    ):
        self.direction = direction  # 'NS' o 'SN'
        self.coordinates = coordinates  # [[lon, lat], ...]
        self.stops = stops  # Lista de dicts de paradas en orden
        self.cumulative_distances = cumulative_distances  # metros
        self.stop_distances = stop_distances  # distancia acumulada de cada parada
        self.total_length_m = cumulative_distances[-1] if cumulative_distances else 0.0

    def get_position_at_distance(self, distance_m: float) -> Tuple[float, float]:
        """
        Retorna (latitud, longitud) para una distancia recorrida en metros.
        """
        return interpolate_position(
            self.coordinates, self.cumulative_distances, distance_m
        )

    def get_stop_distance(self, stop_index: int) -> float:
        """
        Retorna la distancia acumulada (metros) donde se encuentra
        la parada con el índice dado.
        """
        if 0 <= stop_index < len(self.stop_distances):
            return self.stop_distances[stop_index]
        raise IndexError(f"Índice de parada fuera de rango: {stop_index}")

    @property
    def total_length_km(self) -> float:
        return self.total_length_m / 1000.0

    def __repr__(self):
        return (
            f"RouteData(direction={self.direction}, "
            f"stops={len(self.stops)}, "
            f"length={self.total_length_km:.2f} km)"
        )


class RouteManager:
    """
    Gestor central de las rutas geográficas.
    Carga, valida y sirve los datos de la P19.
    """

    def __init__(self):
        self._routes: Dict[str, RouteData] = {}
        self._stops_raw: List[Dict] = []
        self._loaded = False

    def load(self) -> None:
        """
        Carga y valida todos los archivos geográficos.
        Lanza RuntimeError si los archivos son inválidos o inexistentes.
        """
        try:
            self._stops_raw = self._load_stops()
            self._routes["NS"] = self._load_route(
                GEOJSON_NORTH_SOUTH, "NS", direction_key="north_south"
            )
            self._routes["SN"] = self._load_route(
                GEOJSON_SOUTH_NORTH, "SN", direction_key="south_north"
            )
            self._loaded = True
            logger.info(
                "Rutas cargadas: NS=%.2f km, SN=%.2f km",
                self._routes["NS"].total_length_km,
                self._routes["SN"].total_length_km,
            )
        except Exception as e:
            raise RuntimeError(f"Error cargando datos geográficos: {e}") from e

    def _load_stops(self) -> List[Dict]:
        """Carga stops.json y retorna la lista de paradas."""
        with open(STOPS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        stops = data.get("stops", [])
        if not stops:
            raise ValueError("stops.json no contiene paradas")
        logger.info("Paradas cargadas: %d", len(stops))
        return stops

    def _load_route(
        self, filepath: str, direction_code: str, direction_key: str
    ) -> RouteData:
        """
        Carga un archivo GeoJSON de ruta y construye un RouteData.

        Args:
            filepath: Ruta al archivo GeoJSON
            direction_code: 'NS' o 'SN'
            direction_key: 'north_south' o 'south_north'
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Archivo GeoJSON no encontrado: {filepath}")

        with open(filepath, encoding="utf-8") as f:
            geojson = json.load(f)

        if geojson.get("type") != "FeatureCollection":
            raise ValueError(f"GeoJSON inválido en {filepath}: tipo incorrecto")

        features = geojson.get("features", [])
        if not features:
            raise ValueError(f"GeoJSON sin features en {filepath}")

        # Extraer el LineString (primera feature con geometry.type == LineString)
        linestring_coords = None
        for feature in features:
            geom = feature.get("geometry", {})
            if geom.get("type") == "LineString":
                linestring_coords = geom.get("coordinates", [])
                break

        if not linestring_coords or len(linestring_coords) < 2:
            raise ValueError(
                f"No se encontró LineString válido en {filepath}"
            )

        # Validar coordenadas
        self._validate_coordinates(linestring_coords, filepath)

        # Calcular distancias acumuladas
        cum_distances = compute_cumulative_distances(linestring_coords)

        # Extraer paradas en orden para este sentido
        seq_key = f"sequence_{direction_key}"
        stops_for_direction = [
            s for s in self._stops_raw
            if s.get(seq_key) is not None
        ]
        stops_for_direction.sort(key=lambda s: s[seq_key])

        # Proyectar paradas sobre el LineString
        stop_coords = [s["coordinates"] for s in stops_for_direction]
        stop_distances = find_nearest_stop_index(
            linestring_coords, cum_distances, stop_coords
        )

        route = RouteData(
            direction=direction_code,
            coordinates=linestring_coords,
            stops=stops_for_direction,
            cumulative_distances=cum_distances,
            stop_distances=stop_distances,
        )

        logger.info(
            "Ruta %s cargada: %d paradas, %.2f km",
            direction_code, len(stops_for_direction), route.total_length_km
        )
        return route

    def _validate_coordinates(
        self, coordinates: List[List[float]], filepath: str
    ) -> None:
        """
        Valida que las coordenadas estén dentro del área de Bucaramanga/Floridablanca.
        Bounding box: lat [7.0, 7.3], lon [-73.25, -73.0]
        """
        for i, coord in enumerate(coordinates):
            if len(coord) < 2:
                raise ValueError(
                    f"Coordenada {i} inválida en {filepath}: {coord}"
                )
            lon, lat = coord[0], coord[1]
            if not (7.0 <= lat <= 7.3):
                raise ValueError(
                    f"Latitud fuera del área de Bucaramanga en {filepath}, "
                    f"punto {i}: lat={lat}"
                )
            if not (-73.25 <= lon <= -73.0):
                raise ValueError(
                    f"Longitud fuera del área de Bucaramanga en {filepath}, "
                    f"punto {i}: lon={lon}"
                )

    def get_route(self, direction: str) -> RouteData:
        """
        Retorna el RouteData para el sentido dado.

        Args:
            direction: 'NS' (norte-sur) o 'SN' (sur-norte)
        """
        if not self._loaded:
            raise RuntimeError("RouteManager no inicializado. Llama a load() primero.")
        if direction not in self._routes:
            raise ValueError(f"Sentido desconocido: '{direction}'. Use 'NS' o 'SN'.")
        return self._routes[direction]

    def get_all_stops(self) -> List[Dict]:
        """Retorna todas las paradas del archivo stops.json."""
        if not self._loaded:
            raise RuntimeError("RouteManager no inicializado. Llama a load() primero.")
        return self._stops_raw

    def get_center(self) -> Tuple[float, float]:
        """
        Retorna el centro geográfico aproximado de la ruta (latitud, longitud).
        Útil para centrar el mapa inicial.
        """
        return 7.1100, -73.1270

    @property
    def is_loaded(self) -> bool:
        return self._loaded


# Instancia global (singleton) reutilizable
route_manager = RouteManager()
