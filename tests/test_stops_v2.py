import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from data.stops_v2 import validate_inventory


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EXPECTED_AUG_NS = [
    "Café Madrid", "Portal del Norte", "Carrera 15 La Virgen", "Paradas Estaciones del Centro",
    "Puente Peatonal La Rosita", "Centro Comercial La Isla", "Antonia Santos",
    "Estación de Transferencia Provenza Occidental", "Palomitas – Parque San Agustín",
    "FOSUNAB", "Centro Comercial Cañaveral", "Centro Comercial Parque Caracolí"
]
EXPECTED_AUG_SN = [
    "Paralela Cañaveral", "Puente Peatonal Molinos", "Hormigueros", "Payador",
    "Estación de Transferencia Provenza Oriental", "Antonia Santos", "Puerta del Sol",
    "La Isla", "Puente Peatonal La Rosita", "Estaciones del Centro", "Carrera 15",
    "CAI La Virgen", "Colseguros", "Portal del Norte", "Café Madrid"
]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def version(document, version_id):
    return next(v for v in document["versions"] if v["id"] == version_id)


def test_legacy_backup_is_byte_identical_and_hash_matches():
    original = (DATA / "stops.json").read_bytes()
    backup = (DATA / "stops.legacy.json").read_bytes()
    normalized = read_json(DATA / "stops.v2.json")
    assert original == backup
    digest = hashlib.sha256(original).hexdigest()
    assert hashlib.sha256(backup).hexdigest() == digest
    assert normalized["metadata"]["legacy_snapshot"]["sha256"] == digest


def test_all_19_legacy_records_and_fields_are_preserved_exactly():
    original = read_json(DATA / "stops.json")
    normalized = read_json(DATA / "stops.v2.json")
    migrated = {r["legacy_id"]: r["legacy_record"] for r in normalized["legacy_records"]}
    assert len(original["stops"]) == len(normalized["legacy_records"]) == 19
    assert migrated == {record["id"]: record for record in original["stops"]}


def test_normalized_inventory_passes_validator():
    assert validate_inventory(read_json(DATA / "stops.v2.json")) == []


def test_august_textual_mentions_preserve_exact_order_without_stop_identity():
    document = read_json(DATA / "stops.v2.json")
    august = version(document, "p19-2026-08-31")
    ns = august["directions"]["NS"]["mentions"]
    sn = august["directions"]["SN"]["mentions"]
    assert [m["text"] for m in ns] == EXPECTED_AUG_NS
    assert [m["text"] for m in sn] == EXPECTED_AUG_SN
    assert all(m["entity_id"] is None and m["location"] is None for m in ns + sn)
    assert ns[2]["text"] == "Carrera 15 La Virgen"
    assert [m["text"] for m in sn[10:13]] == ["Carrera 15", "CAI La Virgen", "Colseguros"]


def test_q2_is_a_textual_corridor_trace_not_a_stop_inventory():
    q2 = version(read_json(DATA / "stops.v2.json"), "p19-q2-2026")
    assert q2["directions"] == {}
    trace = q2["corridor_trace"]
    assert trace["kind"] == "textual_corridor_trace"
    assert trace["directional_partition"] == "not_stated_unambiguously"
    assert trace["entity_id"] is None and trace["location"] is None


def test_p1_coverage_is_separate_from_may_p19_mentions():
    may = version(read_json(DATA / "stops.v2.json"), "p19-2026-05-31")
    assert len(may["coverage_contexts"]) == 1
    context = may["coverage_contexts"][0]
    assert context["kind"] == "other_service_coverage" and context["service_id"] == "P1"
    assert "carrera 15" in context["text"].lower()
    assert all("centro" not in m["text"].lower()
               for block in may["directions"].values() for m in block["mentions"])


def test_s_n_06_remains_unresolved_and_non_projectable():
    document = read_json(DATA / "stops.v2.json")
    record = next(r for r in document["legacy_records"] if r["legacy_id"] == "S-N-06")
    assert record["identity_status"] == "identity_unresolved"
    assert record["projection_eligible"] is False
    assert record["location"]["coordinates"] == record["legacy_record"]["coordinates"]
    assert record["location"]["confidence"] is None


def test_no_physical_entities_or_new_coordinates_are_inferred_from_names():
    document = read_json(DATA / "stops.v2.json")
    assert document["stop_entities"] == []
    assert all(m["entity_id"] is None and m["location"] is None
               for v in document["versions"]
               for block in v.get("directions", {}).values()
               for m in block["mentions"])
    for record in document["legacy_records"]:
        old = record["legacy_record"]
        assert record["location"]["coordinates"] == old.get("coordinates")
        assert record["location"]["confidence"] is None
        assert record["location"]["legacy_confidence"] == old.get("certainty")


def test_validator_reports_bad_nested_shapes_without_raising():
    for malformed in [None, [], {"schema_version": "2.0", "versions": [None]},
                      {"schema_version": "2.0", "metadata": [], "versions": ["bad"]}]:
        result = validate_inventory(malformed)
        assert result and all(isinstance(message, str) for message in result)


def test_validator_checks_claim_ids_sources_and_location_ranges():
    doc = read_json(DATA / "stops.v2.json")
    doc["versions"][2]["directions"]["SN"]["mentions"][0]["source_id"] = "missing"
    doc["versions"][2]["directions"]["SN"]["mentions"][1]["mention_id"] = \
        doc["versions"][2]["directions"]["SN"]["mentions"][0]["mention_id"]
    doc["legacy_records"][0]["location"]["coordinates"] = [float("nan"), 7]
    errors = validate_inventory(doc)
    assert any("source_id" in e for e in errors)
    assert any("unique" in e for e in errors)
    assert any("finite" in e for e in errors)


def test_generator_is_repeatable_and_does_not_change_inputs():
    with tempfile.TemporaryDirectory(dir=DATA) as temp:
        isolated = Path(temp)
        for name in ("stops.json", "stops.legacy.json", "build_stops_v2.py"):
            shutil.copyfile(DATA / name, isolated / name)
        before = {name: (isolated / name).read_bytes()
                  for name in ("stops.json", "stops.legacy.json")}
        command = [sys.executable, str(isolated / "build_stops_v2.py")]
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        first = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        assert first.returncode == 0, first.stderr
        output_one = (isolated / "stops.v2.json").read_bytes()
        second = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
        assert second.returncode == 0, second.stderr
        output_two = (isolated / "stops.v2.json").read_bytes()
        assert output_one == output_two
        assert hashlib.sha256(output_one).hexdigest() == hashlib.sha256(output_two).hexdigest()
        assert before == {name: (isolated / name).read_bytes() for name in before}


def test_generator_rejects_mismatched_backup_without_changing_any_existing_file():
    with tempfile.TemporaryDirectory(dir=DATA) as temp:
        isolated = Path(temp)
        for name in ("stops.json", "stops.legacy.json", "build_stops_v2.py"):
            shutil.copyfile(DATA / name, isolated / name)
        (isolated / "stops.v2.json").write_bytes(b"previous-output-preserved")
        source_before = (isolated / "stops.json").read_bytes()
        backup_before = (isolated / "stops.legacy.json").read_bytes()
        (isolated / "stops.legacy.json").write_bytes(backup_before + b"different")
        mismatched_backup = (isolated / "stops.legacy.json").read_bytes()
        output_before = (isolated / "stops.v2.json").read_bytes()
        result = subprocess.run([sys.executable, str(isolated / "build_stops_v2.py")],
                                cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)},
                                capture_output=True, text=True)
        assert result.returncode != 0
        assert "differs" in result.stderr
        assert (isolated / "stops.json").read_bytes() == source_before
        assert (isolated / "stops.legacy.json").read_bytes() == mismatched_backup
        assert (isolated / "stops.v2.json").read_bytes() == output_before
