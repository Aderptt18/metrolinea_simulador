"""
map_components.py — Componentes Dash Leaflet para el mapa de la P19.

Genera los elementos visuales del mapa: líneas de ruta, marcadores
de paradas, popups informativos y capa de tiles.
"""

import dash_leaflet as dl
from typing import List, Dict, Optional

# Colores del sistema
COLORS = {
    "route_NS": "#2ecc71",       # Verde — sentido Norte-Sur
    "route_SN": "#3498db",       # Azul — sentido Sur-Norte
    "stop_terminal": "#e74c3c",  # Rojo — terminales
    "stop_transfer": "#e67e22",  # Naranja — estaciones de transferencia
    "stop_regular": "#2c3e50",   # Gris oscuro — paradas regulares
    "stop_pending": "#95a5a6",   # Gris claro — paradas pendientes de validación
    "bus_marker": "#f1c40f",     # Amarillo — buses
}

# Centro del mapa (Bucaramanga / Floridablanca)
MAP_CENTER = [7.1100, -73.1270]
MAP_ZOOM = 13


def build_base_map(
    route_ns_geojson: Optional[Dict] = None,
    route_sn_geojson: Optional[Dict] = None,
    stops: Optional[List[Dict]] = None,
    show_ns: bool = True,
    show_sn: bool = True,
    bus_markers: Optional[List] = None,
) -> dl.Map:
    """
    Construye el componente dl.Map completo con todas las capas.

    Args:
        route_ns_geojson: GeoJSON del recorrido Norte-Sur
        route_sn_geojson: GeoJSON del recorrido Sur-Norte
        stops: Lista de paradas desde stops.json
        show_ns: Si mostrar el recorrido Norte-Sur
        show_sn: Si mostrar el recorrido Sur-Norte
        bus_markers: Lista de marcadores de buses activos

    Returns:
        Componente dl.Map configurado
    """
    layers = [
        dl.TileLayer(
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom=19,
        )
    ]

    # Capa de recorrido Norte-Sur
    if show_ns and route_ns_geojson:
        layers.append(build_route_layer(route_ns_geojson, "NS"))

    # Capa de recorrido Sur-Norte
    if show_sn and route_sn_geojson:
        layers.append(build_route_layer(route_sn_geojson, "SN"))

    # Marcadores de paradas
    if stops:
        for stop_layer in build_stop_markers(stops):
            layers.append(stop_layer)

    # Marcadores de buses
    if bus_markers:
        layers.extend(bus_markers)

    # Leyenda
    layers.append(build_legend())

    return dl.Map(
        id="main-map",
        children=layers,
        center=MAP_CENTER,
        zoom=MAP_ZOOM,
        style={
            "width": "100%",
            "height": "100%",
            "borderRadius": "8px",
        },
        zoomControl=True,
        attributionControl=True,
    )


def build_route_layer(geojson: Dict, direction: str) -> dl.GeoJSON:
    """
    Construye la capa GeoJSON para el trazado de un sentido de la ruta.

    Args:
        geojson: Diccionario GeoJSON con el LineString del recorrido
        direction: 'NS' o 'SN'
    """
    color = COLORS["route_NS"] if direction == "NS" else COLORS["route_SN"]
    label = "Norte→Sur" if direction == "NS" else "Sur→Norte"

    # Filtrar solo el LineString (no los Points/paradas)
    linestring_feature = {
        "type": "FeatureCollection",
        "features": [
            f for f in geojson.get("features", [])
            if f.get("geometry", {}).get("type") == "LineString"
        ]
    }

    return dl.GeoJSON(
        id=f"route-{direction.lower()}",
        data=linestring_feature,
        options={
            "style": {
                "color": color,
                "weight": 5,
                "opacity": 0.85,
                "lineCap": "round",
                "lineJoin": "round",
            }
        },
        hoverStyle={"weight": 7, "opacity": 1.0},
        zoomToBounds=False,
    )


def build_stop_markers(stops: List[Dict]) -> List[dl.Marker]:
    """
    Construye los marcadores de paradas con popups informativos.

    Args:
        stops: Lista de paradas desde stops.json

    Returns:
        Lista de dl.Marker con popup
    """
    markers = []
    seen_ids = set()

    for stop in stops:
        stop_id = stop.get("id", "")
        if stop_id in seen_ids:
            continue
        seen_ids.add(stop_id)

        coords = stop.get("coordinates", [])
        if len(coords) < 2:
            continue

        lon, lat = coords[0], coords[1]
        stop_type = stop.get("type", "BUS_STOP")
        needs_validation = stop.get("needs_validation", True)
        certainty = stop.get("certainty", "LOW")
        name = stop.get("name", "Sin nombre")

        # Determinar color del marcador
        if needs_validation:
            color = COLORS["stop_pending"]
        elif stop_type == "TERMINAL":
            color = COLORS["stop_terminal"]
        elif stop_type == "TRANSFER_STATION":
            color = COLORS["stop_transfer"]
        else:
            color = COLORS["stop_regular"]

        # Icono SVG inline para el marcador
        icon_html = _build_stop_icon_html(color, stop_type)

        # Contenido del popup
        popup_html = _build_stop_popup_html(stop)

        marker = dl.Marker(
            id=f"stop-marker-{stop_id}",
            position=[lat, lon],
            icon={
                "html": icon_html,
                "className": "stop-marker",
                "iconSize": [24, 24],
                "iconAnchor": [12, 12],
            },
            children=dl.Popup(
                children=[popup_html],
                maxWidth=280,
            ),
        )
        markers.append(marker)

    return markers


def _build_stop_icon_html(color: str, stop_type: str) -> str:
    """Genera HTML de ícono SVG para una parada."""
    if stop_type == "TERMINAL":
        # Estrella / círculo grande para terminales
        return (
            f'<div style="width:20px;height:20px;background:{color};'
            f'border-radius:50%;border:3px solid white;'
            f'box-shadow:0 2px 4px rgba(0,0,0,0.5);"></div>'
        )
    elif stop_type == "TRANSFER_STATION":
        # Cuadrado para estaciones de transferencia
        return (
            f'<div style="width:18px;height:18px;background:{color};'
            f'border:3px solid white;transform:rotate(45deg);'
            f'box-shadow:0 2px 4px rgba(0,0,0,0.5);"></div>'
        )
    else:
        # Círculo pequeño para paradas regulares
        return (
            f'<div style="width:14px;height:14px;background:{color};'
            f'border-radius:50%;border:2px solid white;'
            f'box-shadow:0 1px 3px rgba(0,0,0,0.4);"></div>'
        )


def _build_stop_popup_html(stop: Dict) -> str:
    """Genera el HTML del popup de una parada."""
    name = stop.get("name", "Sin nombre")
    stop_type = stop.get("type", "BUS_STOP")
    certainty = stop.get("certainty", "LOW")
    needs_validation = stop.get("needs_validation", True)
    municipality = stop.get("municipality", "N/D")
    notes = stop.get("notes", "")
    address = stop.get("address_reference", "")

    type_labels = {
        "TERMINAL": "🔴 Terminal",
        "TRANSFER_STATION": "🟠 Estación de Transferencia",
        "BUS_STOP": "⚫ Parada",
        "REFERENCE_POINT": "📍 Punto de referencia",
    }
    type_label = type_labels.get(stop_type, stop_type)

    certainty_labels = {
        "HIGH": "✅ Alta",
        "MEDIUM": "🟡 Media",
        "LOW": "⚠️ Baja",
        "PENDING": "❓ Pendiente",
    }
    certainty_label = certainty_labels.get(certainty, certainty)

    validation_badge = (
        '<span style="color:#e74c3c;font-weight:bold;">⚠️ Requiere validación</span>'
        if needs_validation
        else '<span style="color:#2ecc71;">✅ Verificada</span>'
    )

    html = f"""
    <div style="font-family:sans-serif;min-width:220px;">
      <h4 style="margin:0 0 6px;color:#2c3e50;font-size:14px;">{name}</h4>
      <p style="margin:2px 0;font-size:12px;"><b>Tipo:</b> {type_label}</p>
      <p style="margin:2px 0;font-size:12px;"><b>Municipio:</b> {municipality}</p>
      <p style="margin:2px 0;font-size:12px;"><b>Certeza coord.:</b> {certainty_label}</p>
      <p style="margin:2px 0;font-size:12px;"><b>Estado:</b> {validation_badge}</p>
      {"<p style='margin:4px 0;font-size:11px;color:#555;'>" + address + "</p>" if address else ""}
      {"<hr style='margin:4px 0;border-color:#eee;'><p style='margin:2px 0;font-size:10px;color:#777;font-style:italic;'>" + notes + "</p>" if notes else ""}
    </div>
    """
    return html


def build_bus_marker(
    bus_id: str,
    lat: float,
    lon: float,
    direction: str,
    passengers: int,
    capacity: int,
    state: str,
    speed_kmh: float,
) -> dl.Marker:
    """
    Construye un marcador de bus para mostrar en el mapa.

    Args:
        bus_id: Identificador único del bus
        lat, lon: Posición actual
        direction: 'NS' o 'SN'
        passengers: Pasajeros a bordo
        capacity: Capacidad total
        state: Estado actual del bus
        speed_kmh: Velocidad actual

    Returns:
        dl.Marker con ícono de bus y popup informativo
    """
    # Color según ocupación
    occupancy = passengers / capacity if capacity > 0 else 0
    if occupancy >= 0.9:
        bus_color = "#e74c3c"   # Rojo — lleno
    elif occupancy >= 0.6:
        bus_color = "#f39c12"   # Amarillo — semileno
    else:
        bus_color = "#2ecc71"   # Verde — disponible

    direction_arrow = "↓" if direction == "NS" else "↑"
    bus_icon_html = (
        f'<div style="background:{bus_color};color:white;'
        f'width:30px;height:30px;border-radius:6px;'
        f'border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.5);'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-size:16px;font-weight:bold;">{direction_arrow}</div>'
    )

    state_labels = {
        "moving": "🟢 En movimiento",
        "stopped": "🟡 Detenido",
        "boarding": "🔵 Abordando",
        "waiting": "⚫ Esperando salida",
    }
    state_label = state_labels.get(state, state)

    popup_html = f"""
    <div style="font-family:sans-serif;min-width:200px;">
      <h4 style="margin:0 0 6px;color:#2c3e50;">Bus {bus_id}</h4>
      <p style="margin:2px 0;font-size:12px;"><b>Estado:</b> {state_label}</p>
      <p style="margin:2px 0;font-size:12px;"><b>Pasajeros:</b> {passengers}/{capacity}</p>
      <p style="margin:2px 0;font-size:12px;"><b>Ocupación:</b> {occupancy*100:.0f}%</p>
      <p style="margin:2px 0;font-size:12px;"><b>Velocidad:</b> {speed_kmh:.1f} km/h</p>
      <p style="margin:2px 0;font-size:12px;"><b>Sentido:</b> {'Norte→Sur' if direction == 'NS' else 'Sur→Norte'}</p>
    </div>
    """

    return dl.Marker(
        id=f"bus-marker-{bus_id}",
        position=[lat, lon],
        icon={
            "html": bus_icon_html,
            "className": "bus-marker",
            "iconSize": [30, 30],
            "iconAnchor": [15, 15],
        },
        children=dl.Popup(children=[popup_html], maxWidth=250),
    )


def build_legend() -> dl.Marker:
    """
    Construye una leyenda del mapa como marcador HTML fijo.
    Nota: En Dash Leaflet se puede usar un componente personalizado;
    aquí usamos un Marker en la esquina SW del mapa.
    """
    legend_html = """
    <div style="background:rgba(255,255,255,0.92);padding:10px 14px;
                border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,0.2);
                font-family:sans-serif;font-size:12px;min-width:160px;">
      <b style="font-size:13px;color:#2c3e50;">Leyenda</b>
      <div style="margin-top:6px;">
        <span style="display:inline-block;width:30px;height:4px;background:#2ecc71;
                     vertical-align:middle;border-radius:2px;"></span>
        &nbsp;Norte→Sur
      </div>
      <div style="margin-top:4px;">
        <span style="display:inline-block;width:30px;height:4px;background:#3498db;
                     vertical-align:middle;border-radius:2px;"></span>
        &nbsp;Sur→Norte
      </div>
      <div style="margin-top:4px;">
        🔴 Terminal &nbsp;
        🟠 Transferencia
      </div>
      <div style="margin-top:2px;">
        ⚫ Parada &nbsp;
        ⚠️ Pendiente validación
      </div>
    </div>
    """
    return dl.Marker(
        position=[7.0720, -73.1450],
        icon={
            "html": legend_html,
            "className": "legend-marker",
            "iconSize": [180, 100],
            "iconAnchor": [0, 100],
        },
    )
