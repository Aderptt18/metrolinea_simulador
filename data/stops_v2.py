"""Strict validation for the versioned P19 inventory document."""

from __future__ import annotations

import math
from typing import Any

IDENTITY_STATES = {"identity_unresolved", "identity_supported", "not_assessed"}
LOCATION_STATES = {
    "legacy_unverified", "pending", "not_applicable", "mapped_feature",
    "approximate_place_reference", "boarding_location_validated",
}
CONFIDENCE_STATES = {None, "high", "medium", "low"}
EVIDENCE_STATES = {
    "explicit_endpoint", "explicit_route_mention", "explicit_corridor_mention",
    "explicit_group_mention", "not_listed", "unresolved",
}
DIRECTIONS = {"NS", "SN", "unspecified"}
EXPECTED_LEGACY_IDS = {
    "S-N-01", "S-N-02", "S-N-03", "S-N-04", "S-N-05", "S-N-06",
    "S-N-07", "S-N-08", "S-N-09", "S-N-10", "S-N-11", "S-N-12",
    "S-N-13", "S-S-02", "S-S-03", "S-S-04", "S-S-05", "S-S-06", "S-S-08",
}


def _is_object(value: Any) -> bool:
    return isinstance(value, dict)


def validate_inventory(document: Any) -> list[str]:
    """Return readable validation errors instead of leaking malformed-input exceptions."""
    errors: list[str] = []
    try:
        if not _is_object(document):
            return ["document must be an object"]
        if document.get("schema_version") != "2.0":
            errors.append("schema_version must be '2.0'")

        metadata = document.get("metadata")
        if not _is_object(metadata):
            errors.append("metadata must be an object")
            metadata = {}
        if metadata.get("coordinate_reference_system") != "EPSG:4326":
            errors.append("metadata.coordinate_reference_system must be EPSG:4326")
        if metadata.get("coordinate_order") != "longitude_latitude":
            errors.append("metadata.coordinate_order must be longitude_latitude")

        sources = document.get("sources")
        if not _is_object(sources):
            errors.append("sources must be an object")
            sources = {}
        for sid, source in sources.items():
            if not isinstance(sid, str) or not _is_object(source):
                errors.append("each source must have a string ID and object value")
                continue
            if not isinstance(source.get("publisher"), str) or not source["publisher"].strip():
                errors.append(f"source {sid}: publisher is required")
            if not isinstance(source.get("url"), str) or not source["url"].startswith("https://"):
                errors.append(f"source {sid}: an https URL is required")

        legacy_records = document.get("legacy_records")
        if not isinstance(legacy_records, list):
            errors.append("legacy_records must be a list")
            legacy_records = []
        legacy_ids: list[str] = []
        for record in legacy_records:
            if not _is_object(record):
                errors.append("each legacy record must be an object")
                continue
            if record.get("identity_status") != "identity_unresolved":
                errors.append(f"legacy {record.get('legacy_id')}: must remain identity_unresolved")
            if record.get("projection_eligible") is not False:
                errors.append(f"legacy {record.get('legacy_id')}: legacy record cannot be projected")
            original = record.get("legacy_record")
            if not _is_object(original):
                errors.append(f"legacy {record.get('legacy_id')}: legacy_record must be an object")
                continue
            legacy_id = record.get("legacy_id")
            if not isinstance(legacy_id, str) or original.get("id") != legacy_id:
                errors.append("legacy_id must match legacy_record.id")
            else:
                legacy_ids.append(legacy_id)
            if not isinstance(record.get("source_file"), str):
                errors.append(f"legacy {legacy_id}: source_file is required")
            _validate_location(record.get("location"), f"legacy {legacy_id}", errors, legacy=True)
            if isinstance(record.get("location"), dict) and isinstance(original, dict):
                if record["location"].get("coordinates") != original.get("coordinates"):
                    errors.append(f"legacy {legacy_id}: coordinates differ from legacy_record")
        if len(legacy_ids) != len(set(legacy_ids)):
            errors.append("legacy IDs must be unique")
        if set(legacy_ids) != EXPECTED_LEGACY_IDS:
            errors.append("legacy records must contain exactly the 19 expected IDs")

        entities = document.get("stop_entities")
        if not isinstance(entities, list):
            errors.append("stop_entities must be a list")
            entities = []
        entity_ids: list[str] = []
        for entity in entities:
            if not _is_object(entity):
                errors.append("each stop entity must be an object")
                continue
            eid = entity.get("id")
            if not isinstance(eid, str) or not eid:
                errors.append("each stop entity requires a nonempty id")
            else:
                entity_ids.append(eid)
            if entity.get("identity_status") not in IDENTITY_STATES:
                errors.append(f"entity {eid}: invalid identity_status")
            if not isinstance(entity.get("names"), list):
                errors.append(f"entity {eid}: names must be a list")
            _validate_location(entity.get("location"), f"entity {eid}", errors)
        if len(entity_ids) != len(set(entity_ids)):
            errors.append("stop entity IDs must be unique")
        entity_id_set = set(entity_ids)

        versions = document.get("versions")
        if not isinstance(versions, list):
            errors.append("versions must be a list")
            versions = []
        version_ids: list[str] = []
        mention_ids: list[str] = []
        for version in versions:
            if not _is_object(version):
                errors.append("each version must be an object")
                continue
            vid = version.get("id")
            if not isinstance(vid, str) or not vid:
                errors.append("each version requires a nonempty id")
            else:
                version_ids.append(vid)
            if version.get("source_id") not in sources:
                errors.append(f"version {vid}: source_id does not reference a source")
            trace = version.get("corridor_trace")
            if trace is not None:
                if not _is_object(trace):
                    errors.append(f"version {vid}: corridor_trace must be an object")
                else:
                    _validate_claim(trace, vid, sources, entity_id_set, mention_ids, errors,
                                    require_location=False, allow_entity_ref=False)
                    if trace.get("kind") != "textual_corridor_trace":
                        errors.append(f"version {vid}: corridor_trace.kind must be textual_corridor_trace")
            coverage = version.get("coverage_contexts", [])
            if not isinstance(coverage, list):
                errors.append(f"version {vid}: coverage_contexts must be a list")
                coverage = []
            for context in coverage:
                _validate_claim(context, vid, sources, entity_id_set, mention_ids, errors,
                                require_location=False, allow_entity_ref=False)
                if _is_object(context) and context.get("kind") != "other_service_coverage":
                    errors.append(f"version {vid}: invalid coverage context kind")
            directions = version.get("directions")
            if not _is_object(directions):
                errors.append(f"version {vid}: directions must be an object")
                continue
            for direction, block in directions.items():
                if direction not in DIRECTIONS:
                    errors.append(f"version {vid}: invalid direction {direction}")
                if not _is_object(block) or not isinstance(block.get("mentions"), list):
                    errors.append(f"version {vid}/{direction}: mentions must be a list")
                    continue
                for mention in block["mentions"]:
                    _validate_claim(mention, vid, sources, entity_id_set, mention_ids, errors,
                                    require_location=True, allow_entity_ref=True)
        if len(version_ids) != len(set(version_ids)):
            errors.append("version IDs must be unique")
        if len(mention_ids) != len(set(mention_ids)):
            errors.append("mention IDs must be unique across the document")
        academic = metadata.get("academic_reference_version")
        if academic not in version_ids:
            errors.append("academic_reference_version must reference a declared version")
    except Exception as exc:  # malformed nested input should become a useful diagnostic
        errors.append(f"malformed document structure: {type(exc).__name__}: {exc}")
    return errors


def _validate_claim(claim, version_id, sources, entity_ids, mention_ids, errors,
                    require_location, allow_entity_ref):
    label = claim.get("mention_id", claim.get("id", version_id)) if _is_object(claim) else version_id
    if not _is_object(claim):
        errors.append(f"{label}: claim must be an object")
        return
    claim_id = claim.get("mention_id", claim.get("id"))
    if not isinstance(claim_id, str) or not claim_id:
        errors.append(f"{label}: claim ID is required")
    else:
        mention_ids.append(claim_id)
    if not isinstance(claim.get("text"), str) or not claim["text"].strip():
        errors.append(f"{label}: original text is required")
    if claim.get("source_id") not in sources:
        errors.append(f"{label}: source_id does not reference a source")
    if claim.get("evidence_status") not in EVIDENCE_STATES:
        errors.append(f"{label}: invalid evidence_status")
    entity_id = claim.get("entity_id")
    if entity_id is not None and (not allow_entity_ref or entity_id not in entity_ids):
        errors.append(f"{label}: entity_id is not a valid resolved entity")
    order = claim.get("textual_order")
    basis = claim.get("order_basis")
    if order is not None and (not isinstance(order, int) or isinstance(order, bool) or order < 1):
        errors.append(f"{label}: textual_order must be a positive integer or null")
    if order is not None and basis != "source_text_order":
        errors.append(f"{label}: textual_order must be marked source_text_order")
    if basis not in {None, "source_text_order"}:
        errors.append(f"{label}: invalid order_basis")
    if require_location and entity_id is None and claim.get("location") is not None:
        errors.append(f"{label}: unresolved mention cannot have location")
    if claim.get("location") is not None:
        _validate_location(claim["location"], label, errors)


def _validate_location(location, label, errors, legacy=False):
    if not _is_object(location):
        errors.append(f"{label}: location must be an object")
        return
    status = location.get("location_status")
    if status not in LOCATION_STATES:
        errors.append(f"{label}: invalid location_status")
    if location.get("confidence") not in CONFIDENCE_STATES:
        errors.append(f"{label}: invalid normalized confidence")
    if location.get("crs") != "EPSG:4326" or location.get("order") != "longitude_latitude":
        errors.append(f"{label}: location CRS/order must be EPSG:4326 longitude_latitude")
    coords = location.get("coordinates")
    if coords is None:
        if status not in {"pending", "not_applicable"}:
            errors.append(f"{label}: null coordinates require pending/not_applicable")
        if location.get("confidence") is not None:
            errors.append(f"{label}: null coordinates require null confidence")
    elif not (isinstance(coords, list) and len(coords) == 2):
        errors.append(f"{label}: coordinates must be null or a [longitude, latitude] pair")
    else:
        lon, lat = coords
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) for v in coords):
            errors.append(f"{label}: coordinates must be finite numbers")
        elif not (-180 <= lon <= 180 and -90 <= lat <= 90):
            errors.append(f"{label}: coordinates outside EPSG:4326 bounds")
        if status in {"pending", "not_applicable"}:
            errors.append(f"{label}: coordinates cannot be present with {status}")
    if not isinstance(location.get("evidence"), list):
        errors.append(f"{label}: location evidence must be a list")
    if legacy and location.get("confidence") is not None:
        errors.append(f"{label}: legacy location cannot have normalized confidence")
    if legacy and location.get("location_status") == "boarding_location_validated":
        errors.append(f"{label}: legacy location cannot be boarding-location validated")
