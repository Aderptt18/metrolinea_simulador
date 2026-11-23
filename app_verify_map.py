"""
app_verify_map.py — Visualización preliminar de verificación geográfica.

Aplicación Dash mínima para comprobar que:
1. Los archivos GeoJSON se cargan correctamente.
2. Los recorridos N→S y S→N se muestran sobre el mapa real.
3. Las paradas aparecen en sus ubicaciones correctas.
4. Los popups muestran la información de certeza y validación.

EJECUTAR:
    python app_verify_map.py

Luego abrir: http://localhost:8050
"""

import json
import logging
import os
import sys

# Asegurar que el directorio raíz esté en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dash
from dash import html, dcc
import dash_leaflet as dl

from map.route_manager import route_manager
from map.map_components import (
    MAP_CENTER, MAP_ZOOM, COLORS,
    build_route_layer, build_stop_markers, build_legend
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cargar datos geográficos
# ---------------------------------------------------------------------------
try:
    route_manager.load()
    logger.info("Rutas cargadas correctamente")
except Exception as e:
    logger.error("Error cargando rutas: %s", e)
    sys.exit(1)

# Cargar GeoJSON directamente para Dash Leaflet
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

with open(os.path.join(DATA_DIR, "route_p19_north_south.geojson"), encoding="utf-8") as f:
    geojson_ns = json.load(f)

with open(os.path.join(DATA_DIR, "route_p19_south_north.geojson"), encoding="utf-8") as f:
    geojson_sn = json.load(f)

stops = route_manager.get_all_stops()

# ---------------------------------------------------------------------------
# Construir el mapa
# ---------------------------------------------------------------------------

# Filtrar solo LineStrings para las rutas
def extract_linestring(geojson):
    return {
        "type": "FeatureCollection",
        "features": [
            f for f in geojson.get("features", [])
            if f.get("geometry", {}).get("type") == "LineString"
        ]
    }

# Estadísticas de las rutas
route_ns = route_manager.get_route("NS")
route_sn = route_manager.get_route("SN")

# Construir capas del mapa
map_layers = [
    dl.TileLayer(
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom=19,
    ),
    # Recorrido Norte-Sur (verde)
    dl.GeoJSON(
        id="route-ns",
        data=extract_linestring(geojson_ns),
        options={
            "style": {
                "color": COLORS["route_NS"],
                "weight": 5,
                "opacity": 0.85,
            }
        },
    ),
    # Recorrido Sur-Norte (azul)
    dl.GeoJSON(
        id="route-sn",
        data=extract_linestring(geojson_sn),
        options={
            "style": {
                "color": COLORS["route_SN"],
                "weight": 5,
                "opacity": 0.85,
                "dashArray": "8, 4",
            }
        },
    ),
]

# Agregar marcadores de paradas
map_layers.extend(build_stop_markers(stops))

# Mapa principal
main_map = dl.Map(
    id="verify-map",
    children=map_layers,
    center=MAP_CENTER,
    zoom=MAP_ZOOM,
    style={"width": "100%", "height": "600px", "borderRadius": "8px"},
)

# ---------------------------------------------------------------------------
# Estadísticas para el panel de información
# ---------------------------------------------------------------------------
stops_ns = [s for s in stops if s.get("sequence_north_south") is not None]
stops_sn = [s for s in stops if s.get("sequence_south_north") is not None]
stops_needs_validation = [s for s in stops if s.get("needs_validation")]
stops_high = [s for s in stops if s.get("certainty") == "HIGH"]
stops_medium = [s for s in stops if s.get("certainty") == "MEDIUM"]
stops_low = [s for s in stops if s.get("certainty") == "LOW"]

# ---------------------------------------------------------------------------
# Layout de la aplicación
# ---------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    title="Metrolinea Simulator — Verificación Geográfica P19",
    suppress_callback_exceptions=True,
)

app.layout = html.Div(
    style={
        "fontFamily": "Segoe UI, Arial, sans-serif",
        "background": "#f5f7fa",
        "minHeight": "100vh",
        "padding": "0",
    },
    children=[
        # Encabezado
        html.Div(
            style={
                "background": "linear-gradient(135deg, #1a252f, #2c3e50)",
                "padding": "16px 24px",
                "color": "white",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "space-between",
            },
            children=[
                html.Div([
                    html.H1(
                        "🚌 Metrolinea Simulator",
                        style={"margin": "0", "fontSize": "22px", "fontWeight": "700"},
                    ),
                    html.P(
                        "Ruta P19 — Verificación Geográfica | Café Madrid ↔ Cañaveral / FOSUNAB",
                        style={"margin": "4px 0 0", "fontSize": "13px", "color": "#bdc3c7"},
                    ),
                ]),
                html.Div(
                    style={
                        "background": "#27ae60",
                        "padding": "6px 14px",
                        "borderRadius": "20px",
                        "fontSize": "13px",
                        "fontWeight": "600",
                    },
                    children="✅ Etapa 1 — Verificación Geográfica"
                ),
            ],
        ),

        # Contenido principal
        html.Div(
            style={"padding": "16px 24px"},
            children=[

                # Aviso de limitaciones
                html.Div(
                    style={
                        "background": "#fef9e7",
                        "border": "1px solid #f39c12",
                        "borderLeft": "4px solid #f39c12",
                        "borderRadius": "6px",
                        "padding": "12px 16px",
                        "marginBottom": "16px",
                        "fontSize": "13px",
                        "color": "#7d6608",
                    },
                    children=[
                        html.Strong("⚠️ Nota de verificación geográfica: "),
                        "Las coordenadas de las paradas son derivadas de fuentes públicas (OSM, Moovit, mapcarta). "
                        "No son coordenadas oficiales de Metrolínea S.A. Las paradas marcadas en gris "
                        "requieren validación. El trazado sigue calles reales pero es una aproximación. "
                        "Ver assumptions.json para el detalle completo de certeza por parada."
                    ]
                ),

                # Fila: Mapa + Panel lateral
                html.Div(
                    style={"display": "flex", "gap": "16px", "alignItems": "flex-start"},
                    children=[

                        # Mapa
                        html.Div(
                            style={"flex": "1"},
                            children=[main_map]
                        ),

                        # Panel de estadísticas
                        html.Div(
                            style={
                                "width": "280px",
                                "flexShrink": "0",
                            },
                            children=[

                                # Estadísticas de ruta
                                _stat_card("📐 Recorrido Norte→Sur", [
                                    ("Longitud aprox.", f"{route_ns.total_length_km:.1f} km"),
                                    ("Paradas", f"{len(stops_ns)}"),
                                    ("Terminales / Transferencia",
                                     f"{len([s for s in stops_ns if s['type'] in ('TERMINAL', 'TRANSFER_STATION')])}"),
                                ], border_color=COLORS["route_NS"]),

                                _stat_card("📐 Recorrido Sur→Norte", [
                                    ("Longitud aprox.", f"{route_sn.total_length_km:.1f} km"),
                                    ("Paradas", f"{len(stops_sn)}"),
                                    ("Terminales / Transferencia",
                                     f"{len([s for s in stops_sn if s['type'] in ('TERMINAL', 'TRANSFER_STATION')])}"),
                                ], border_color=COLORS["route_SN"]),

                                _stat_card("🎯 Certeza de coordenadas", [
                                    ("Alta (verificada)", f"{len(stops_high)} paradas"),
                                    ("Media (OSM/geocodificación)", f"{len(stops_medium)} paradas"),
                                    ("Baja (estimada)", f"{len(stops_low)} paradas"),
                                    ("Requieren validación", f"{len(stops_needs_validation)} paradas"),
                                ], border_color="#e74c3c"),

                                # Leyenda visual
                                html.Div(
                                    style={
                                        "background": "white",
                                        "borderRadius": "8px",
                                        "padding": "12px 14px",
                                        "marginBottom": "12px",
                                        "boxShadow": "0 1px 4px rgba(0,0,0,0.1)",
                                        "fontSize": "13px",
                                    },
                                    children=[
                                        html.Strong("Leyenda del mapa"),
                                        html.Div(style={"marginTop": "8px"}, children=[
                                            _legend_item("━━━", COLORS["route_NS"], "Recorrido Norte→Sur"),
                                            _legend_item("╌╌╌", COLORS["route_SN"], "Recorrido Sur→Norte"),
                                            _legend_item("●", COLORS["stop_terminal"], "Terminal"),
                                            _legend_item("◆", COLORS["stop_transfer"], "Estación transferencia"),
                                            _legend_item("●", COLORS["stop_regular"], "Parada regular"),
                                            _legend_item("●", COLORS["stop_pending"], "Pendiente validación"),
                                        ])
                                    ]
                                ),

                                html.Div(
                                    style={"fontSize": "11px", "color": "#95a5a6", "textAlign": "center"},
                                    children="Haz clic en cualquier parada para ver su información de certeza"
                                ),
                            ]
                        ),
                    ]
                ),

                # Tabla de paradas
                html.Div(
                    style={"marginTop": "20px"},
                    children=[
                        html.H3(
                            "Inventario de paradas verificadas",
                            style={"color": "#2c3e50", "marginBottom": "10px", "fontSize": "16px"}
                        ),
                        _build_stops_table(stops),
                    ]
                ),
            ]
        ),
    ]
)


def _stat_card(title: str, items: list, border_color: str = "#3498db") -> html.Div:
    """Tarjeta de estadísticas."""
    rows = [
        html.Div(
            style={
                "display": "flex", "justifyContent": "space-between",
                "padding": "3px 0", "fontSize": "12px",
                "borderBottom": "1px solid #f0f0f0",
            },
            children=[
                html.Span(label, style={"color": "#666"}),
                html.Span(value, style={"fontWeight": "600", "color": "#2c3e50"}),
            ]
        )
        for label, value in items
    ]
    return html.Div(
        style={
            "background": "white",
            "borderRadius": "8px",
            "padding": "12px 14px",
            "marginBottom": "12px",
            "boxShadow": "0 1px 4px rgba(0,0,0,0.1)",
            "borderLeft": f"4px solid {border_color}",
        },
        children=[
            html.Strong(title, style={"fontSize": "13px", "color": "#2c3e50"}),
            html.Div(style={"marginTop": "8px"}, children=rows),
        ]
    )


def _legend_item(symbol: str, color: str, label: str) -> html.Div:
    return html.Div(
        style={"display": "flex", "alignItems": "center", "marginBottom": "4px"},
        children=[
            html.Span(symbol, style={"color": color, "marginRight": "8px", "fontWeight": "bold"}),
            html.Span(label, style={"fontSize": "12px", "color": "#555"}),
        ]
    )


def _build_stops_table(stops: list) -> html.Div:
    """Construye una tabla HTML de paradas."""
    header = html.Tr([
        html.Th(col, style={"padding": "8px 12px", "background": "#2c3e50",
                            "color": "white", "fontSize": "12px", "fontWeight": "600"})
        for col in ["ID", "Nombre", "Tipo", "Municipio", "Certeza", "Validación", "Coord. (lat, lon)"]
    ])

    rows = []
    for stop in stops:
        needs_val = stop.get("needs_validation", True)
        certainty = stop.get("certainty", "LOW")
        coords = stop.get("coordinates", [None, None])

        certainty_colors = {"HIGH": "#27ae60", "MEDIUM": "#f39c12", "LOW": "#e74c3c"}
        cert_color = certainty_colors.get(certainty, "#95a5a6")

        row = html.Tr(
            style={"borderBottom": "1px solid #eee"},
            children=[
                html.Td(stop.get("id", ""), style={"padding": "6px 12px", "fontSize": "11px", "color": "#666"}),
                html.Td(stop.get("name", ""), style={"padding": "6px 12px", "fontSize": "12px", "fontWeight": "500"}),
                html.Td(stop.get("type", ""), style={"padding": "6px 12px", "fontSize": "11px"}),
                html.Td(stop.get("municipality", ""), style={"padding": "6px 12px", "fontSize": "11px"}),
                html.Td(
                    certainty,
                    style={"padding": "6px 12px", "fontSize": "11px",
                           "color": cert_color, "fontWeight": "600"}
                ),
                html.Td(
                    "⚠️ Pendiente" if needs_val else "✅ OK",
                    style={"padding": "6px 12px", "fontSize": "11px",
                           "color": "#e74c3c" if needs_val else "#27ae60"}
                ),
                html.Td(
                    f"{coords[1]:.5f}, {coords[0]:.5f}" if coords[0] and coords[1] else "N/A",
                    style={"padding": "6px 12px", "fontSize": "11px", "fontFamily": "monospace", "color": "#555"}
                ),
            ]
        )
        rows.append(row)

    return html.Div(
        style={"overflowX": "auto"},
        children=[
            html.Table(
                style={
                    "width": "100%",
                    "borderCollapse": "collapse",
                    "background": "white",
                    "borderRadius": "8px",
                    "boxShadow": "0 1px 4px rgba(0,0,0,0.1)",
                    "overflow": "hidden",
                    "fontSize": "12px",
                },
                children=[
                    html.Thead(header),
                    html.Tbody(rows),
                ]
            )
        ]
    )


if __name__ == "__main__":
    print("=" * 60)
    print("Metrolinea Simulator — Verificación Geográfica")
    print("Ruta P19: Café Madrid ↔ Cañaveral / FOSUNAB")
    print("=" * 60)
    print(f"Recorrido N→S: {route_ns.total_length_km:.2f} km, {len(stops_ns)} paradas")
    print(f"Recorrido S→N: {route_sn.total_length_km:.2f} km, {len(stops_sn)} paradas")
    print(f"Total paradas únicas: {len(stops)}")
    print(f"Requieren validación: {len(stops_needs_validation)}")
    print("-" * 60)
    print("Abriendo en: http://localhost:8050")
    print("=" * 60)
    app.run(debug=True, host="0.0.0.0", port=8050)
