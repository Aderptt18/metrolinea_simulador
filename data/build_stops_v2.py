"""Build a reproducible v2 document without changing either legacy input."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

try:
    from data.stops_v2 import validate_inventory
except ModuleNotFoundError:  # direct execution from inside data/
    from stops_v2 import validate_inventory

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "stops.json"
BACKUP = ROOT / "stops.legacy.json"
OUTPUT = ROOT / "stops.v2.json"

SOURCE_BYTES = SOURCE.read_bytes()
BACKUP_BYTES = BACKUP.read_bytes()
if SOURCE_BYTES != BACKUP_BYTES:
    raise SystemExit("Legacy backup differs from stops.json; refusing to write v2")

legacy_document = json.loads(SOURCE_BYTES.decode("utf-8"))
legacy_stops = legacy_document.get("stops")
if not isinstance(legacy_stops, list) or len(legacy_stops) != 19:
    raise SystemExit("stops.json must contain the expected 19 legacy records")
if any(not isinstance(stop, dict) or not isinstance(stop.get("id"), str) for stop in legacy_stops):
    raise SystemExit("stops.json contains a malformed legacy record")
if len({stop["id"] for stop in legacy_stops}) != 19:
    raise SystemExit("stops.json legacy IDs must be unique")

digest = hashlib.sha256(SOURCE_BYTES).hexdigest()
sources = {
    "metrolinea-2026-05-29": {
        "publisher": "Metrolínea", "published_at": "2026-05-29",
        "url": "https://www.metrolinea.gov.co/v3.0/sitme-ajusta-sus-rutas-para-servirle-mejor-partir-del-31-de-mayo-2283",
        "source_type": "official_operational_announcement"
    },
    "metrolinea-q2-2026": {
        "publisher": "Metrolínea", "published_at": None, "period": "2026-Q2",
        "url": "https://mail.metrolinea.gov.co/v3.0/sites/default/files/informe_de_gestion_2_trim_2026_con_anexos.pdf",
        "source_type": "official_management_report"
    },
    "alcaldia-2026-08-31": {
        "publisher": "Alcaldía de Bucaramanga", "published_at": "2026-08-31",
        "url": "https://www.bucaramanga.gov.co/noticias/ruta-complementaria-p19-incorpora-nuevos-medios-de-pago-y-fortalece/",
        "source_type": "official_publication"
    }
}

def claim(claim_id, text, source_id, evidence_status, order=None, kind=None):
    return {
        "mention_id": claim_id, "text": text, "source_id": source_id,
        "evidence_status": evidence_status, "textual_order": order,
        "order_basis": "source_text_order" if order is not None else None,
        "entity_id": None, "location": None, **({"kind": kind} if kind else {})
    }

may = {
    "id": "p19-2026-05-31", "source_id": "metrolinea-2026-05-29",
    "directions": {
        "NS": {"mentions": [
            claim("may-ns-01", "Portal Norte", "metrolinea-2026-05-29", "explicit_endpoint"),
            claim("may-ns-02", "Estación Provenza Occidental", "metrolinea-2026-05-29", "explicit_endpoint")]},
        "SN": {"mentions": [
            claim("may-sn-01", "Portal Norte", "metrolinea-2026-05-29", "explicit_endpoint"),
            claim("may-sn-02", "Estación Provenza Oriental", "metrolinea-2026-05-29", "explicit_endpoint")]}
    },
    "coverage_contexts": [{
        **claim("may-p1-center", "conexión hacia y desde el centro de Bucaramanga por la carrera 15",
                "metrolinea-2026-05-29", "explicit_corridor_mention"),
        "kind": "other_service_coverage", "service_id": "P1"
    }]
}

q2_trace_text = (
    "Café Madrid – Villa Alegría – Kennedy – Hospital del Norte – Portal Norte – "
    "Vía al mar Bucaramanga – Cra 15 – Estación San Mateo – Diagonal 15 – "
    "Viaducto García Cadena – Estación Provenza Occidental – Paralela al Bosque – "
    "Calle 146 – Cra 22 – Palomitas – Calle 157 – Calle 29 – Cra 25 – "
    "Centro Comercial Cañaveral – Centro Comercial Caracolí – Paralela autopista "
    "Floridablanca Bucaramanga – Estación Provenza Oriental – Viaducto García Cadena – "
    "Diagonal 15 – Cra 15 – Estación San Mateo – Cra 15 – Vía al Mar Rionegro – "
    "Portal Norte – Kennedy – Villa Alegría – Café Madrid."
)
q2 = {
    "id": "p19-q2-2026", "source_id": "metrolinea-q2-2026",
    "directions": {},
    "corridor_trace": {
        "id": "q2-p19-textual-trace", "kind": "textual_corridor_trace",
        "text": q2_trace_text, "source_id": "metrolinea-q2-2026",
        "evidence_status": "explicit_corridor_mention", "textual_order": None,
        "order_basis": None, "entity_id": None, "location": None,
        "directional_partition": "not_stated_unambiguously"
    },
    "coverage_contexts": []
}

ns_text = [
    "Café Madrid", "Portal del Norte", "Carrera 15 La Virgen", "Paradas Estaciones del Centro",
    "Puente Peatonal La Rosita", "Centro Comercial La Isla", "Antonia Santos",
    "Estación de Transferencia Provenza Occidental", "Palomitas – Parque San Agustín",
    "FOSUNAB", "Centro Comercial Cañaveral", "Centro Comercial Parque Caracolí"
]
sn_text = [
    "Paralela Cañaveral", "Puente Peatonal Molinos", "Hormigueros", "Payador",
    "Estación de Transferencia Provenza Oriental", "Antonia Santos", "Puerta del Sol",
    "La Isla", "Puente Peatonal La Rosita", "Estaciones del Centro", "Carrera 15",
    "CAI La Virgen", "Colseguros", "Portal del Norte", "Café Madrid"
]
august = {
    "id": "p19-2026-08-31", "source_id": "alcaldia-2026-08-31",
    "directions": {
        direction: {"mentions": [claim(f"aug-{direction.lower()}-{i:02}", text,
            "alcaldia-2026-08-31",
            "explicit_group_mention" if "Estaciones del Centro" in text else "explicit_route_mention",
            i) for i, text in enumerate(names, 1)]}
        for direction, names in (("NS", ns_text), ("SN", sn_text))
    },
    "coverage_contexts": []
}

legacy_records = []
for old in legacy_stops:
    coords = old.get("coordinates")
    location = {
        "coordinates": coords, "crs": "EPSG:4326", "order": "longitude_latitude",
        "location_status": "legacy_unverified" if coords is not None else "pending",
        "confidence": None, "legacy_confidence": old.get("certainty"),
        "evidence": [{"source_id": None, "claim": "inherited_from_legacy_record",
                      "object_or_query": None}]
    }
    legacy_records.append({
        "legacy_id": old["id"], "source_file": "stops.json",
        "identity_status": "identity_unresolved", "projection_eligible": False,
        "location": location, "legacy_record": old
    })

document = {
    "schema_version": "2.0",
    "metadata": {
        "route_id": "P19", "coordinate_reference_system": "EPSG:4326",
        "coordinate_order": "longitude_latitude", "academic_reference_version": "p19-2026-08-31",
        "legacy_snapshot": {"file": "stops.legacy.json", "source_file": "stops.json", "sha256": digest},
        "notes": "Textual order is not spatial progression. No source here resolves legacy point identities or validates boarding locations."
    },
    "sources": sources,
    "versions": [may, q2, august],
    "stop_entities": [],
    "legacy_records": legacy_records
}

errors = validate_inventory(document)
if errors:
    raise SystemExit("Generated document failed validation:\n- " + "\n- ".join(errors))

payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
# Validate before touching output, then replace atomically. Rejection leaves any
# previous output and both source files untouched.
fd, temp_name = tempfile.mkstemp(prefix="stops-v2-", suffix=".tmp", dir=ROOT)
try:
    with os.fdopen(fd, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_name, OUTPUT)
finally:
    if os.path.exists(temp_name):
        os.unlink(temp_name)

print(f"Wrote {OUTPUT.name}; legacy_records={len(legacy_records)}; source_sha256={digest}")
