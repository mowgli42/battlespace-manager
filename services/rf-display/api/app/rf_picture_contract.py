"""RF operator picture JSON contract for /api/picture and SSE stream."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.rf_deconfliction import detect_rf_conflicts

RF_PICTURE_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "sim_minutes",
        "commlinks",
        "emitters",
        "ew_platforms",
        "emcon_areas",
        "spectrum",
        "conflicts",
        "deconfliction_summary",
    }
)

RF_PICTURE_TYPED_KEYS: dict[str, type | tuple[type, ...]] = {
    "sim_minutes": (int, float),
    "commlinks": dict,
    "emitters": list,
    "ew_platforms": list,
    "emcon_areas": list,
    "spectrum": dict,
    "conflicts": list,
    "deconfliction_summary": dict,
}

_REPO_ROOT = Path(__file__).resolve().parents[4]
_EMITTER_CATALOG = _REPO_ROOT / "fixtures" / "rf-emitter-catalog-v1.json"
_EMCON_AREAS = _REPO_ROOT / "fixtures" / "rf-emcon-areas-v1.json"

_RADAR_KEYWORDS = ("RADAR", "SAM", "FIRE_CONTROL", "ACQUISITION")
_EW_CAPABILITIES = frozenset({"EW_SUPPORT", "SEAD"})


def _load_json_fixture(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog_entry(catalog: dict[str, Any], key: str) -> dict[str, Any]:
    emitters = catalog.get("emitters") or {}
    entry = emitters.get(key)
    if entry:
        return dict(entry)
    for name, spec in emitters.items():
        if key.upper() in name.upper() or name.upper() in key.upper():
            return dict(spec)
    return {}


def _infer_comm_spec(catalog: dict[str, Any], link: dict[str, Any]) -> dict[str, Any]:
    subtype = (link.get("subtype") or "").upper()
    link_type = (link.get("type") or "").upper()
    if "KA" in subtype or link.get("frequency_mhz", 0) > 10000:
        return _catalog_entry(catalog, "SATCOM_KA")
    if "L-BAND" in subtype or "IRIDIUM" in subtype:
        return _catalog_entry(catalog, "SATCOM_L")
    if "HF" in subtype or link_type == "HF":
        return _catalog_entry(catalog, "HF_NET")
    if "VHF" in subtype or float(link.get("frequency_mhz") or 0) < 200:
        return _catalog_entry(catalog, "VHF_MARINE")
    if "LINK" in subtype or "DATALINK" in link_type:
        return _catalog_entry(catalog, "LINK16")
    return {}


def validate_rf_picture(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["payload must be a dict"]

    for key in sorted(RF_PICTURE_REQUIRED_KEYS - set(payload.keys())):
        errors.append(f"missing required key: {key}")

    for key, expected in RF_PICTURE_TYPED_KEYS.items():
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(expected, tuple):
            if not isinstance(value, expected):
                errors.append(f"{key} must be {expected}, got {type(value).__name__}")
        elif not isinstance(value, expected):
            errors.append(f"{key} must be {expected.__name__}, got {type(value).__name__}")
    return errors


def assert_rf_picture_contract(payload: dict[str, Any]) -> None:
    errors = validate_rf_picture(payload)
    if errors:
        raise AssertionError("; ".join(errors))


def _build_emitters_from_cues(
    cues: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    emitters: list[dict[str, Any]] = []
    seen: set[str] = set()

    for cue in cues:
        emitter_type = cue.get("type") or cue.get("emitter_or_target_type") or "UNKNOWN"
        if emitter_type in seen:
            continue
        spec = _catalog_entry(catalog, emitter_type)
        if not spec and not any(k in emitter_type.upper() for k in _RADAR_KEYWORDS):
            continue
        seen.add(emitter_type)
        emitters.append(
            {
                "emitter_id": cue.get("report_id") or f"cue-{emitter_type}",
                "emitter_type": emitter_type,
                "label": spec.get("label", emitter_type.replace("_", " ").title()),
                "emitter_class": spec.get("emitter_class", "radar" if "RADAR" in emitter_type else "unknown"),
                "affiliation": spec.get("affiliation", "hostile"),
                "band": spec.get("band"),
                "frequency_mhz": spec.get("frequency_mhz"),
                "bandwidth_mhz": spec.get("bandwidth_mhz"),
                "latitude": cue.get("latitude"),
                "longitude": cue.get("longitude"),
                "confidence": cue.get("confidence"),
                "source_feed": cue.get("source_feed"),
                "target_entity_id": cue.get("target_entity_id"),
                "sim_minutes": cue.get("sim_minutes"),
            }
        )

    for ent in entities:
        ptype = (ent.get("platform_type") or "").upper()
        if ent.get("affiliation") != "OPFOR":
            continue
        if not any(k in ptype for k in _RADAR_KEYWORDS + ("SAM",)):
            continue
        eid = ent.get("entity_id", "")
        if eid in seen:
            continue
        spec = _catalog_entry(catalog, ptype)
        seen.add(eid)
        emitters.append(
            {
                "emitter_id": eid,
                "emitter_type": ptype,
                "label": spec.get("label", ent.get("platform_type", eid)),
                "emitter_class": "radar",
                "affiliation": "hostile",
                "band": spec.get("band"),
                "frequency_mhz": spec.get("frequency_mhz"),
                "bandwidth_mhz": spec.get("bandwidth_mhz"),
                "latitude": ent.get("latitude"),
                "longitude": ent.get("longitude"),
                "confidence": ent.get("confidence"),
                "source_feed": "entity_track",
                "target_entity_id": eid,
            }
        )
    return emitters


def _build_ew_platforms(
    scenario: dict[str, Any],
    platforms: list[dict[str, Any]],
    catalog: dict[str, Any],
    sim_minutes: float,
) -> list[dict[str, Any]]:
    ew_rows: list[dict[str, Any]] = []
    coalition = scenario.get("coalitionPlatforms") or []
    ew_by_id = {
        p["platformId"]: p
        for p in coalition
        if "EW" in (p.get("role") or "").upper() or _EW_CAPABILITIES.intersection(p.get("capabilities") or [])
    }

    for plat in platforms:
        pid = plat.get("platform_id", "")
        scenario_plat = ew_by_id.get(pid)
        if scenario_plat is None and plat.get("operational_role", "").upper() != "EW":
            continue
        ptype = plat.get("platform_type") or (scenario_plat or {}).get("type", "EF-111")
        spec = _catalog_entry(catalog, ptype)
        task_role = (plat.get("task_role") or "").upper()
        jamming_active = task_role in ("SEAD", "EW_SUPPORT") or bool(scenario_plat)
        ew_rows.append(
            {
                "platform_id": pid,
                "callsign": plat.get("callsign"),
                "platform_type": ptype,
                "latitude": plat.get("latitude"),
                "longitude": plat.get("longitude"),
                "operational_role": plat.get("operational_role") or (scenario_plat or {}).get("role", "EW"),
                "jamming_active": jamming_active,
                "jam_mode": spec.get("jam_mode", "noise"),
                "band": spec.get("band"),
                "frequency_mhz": spec.get("frequency_mhz"),
                "bandwidth_mhz": spec.get("bandwidth_mhz"),
                "coverage_nm": 80 if ptype == "EF-111" else 40,
                "active_task_id": plat.get("active_task_id"),
                "task_role": plat.get("task_role"),
                "readiness": plat.get("readiness"),
            }
        )

    for pid, scenario_plat in ew_by_id.items():
        if any(r["platform_id"] == pid for r in ew_rows):
            continue
        pos = scenario_plat.get("initialPosition") or {}
        ptype = scenario_plat.get("type", "EF-111")
        spec = _catalog_entry(catalog, ptype)
        ew_rows.append(
            {
                "platform_id": pid,
                "callsign": scenario_plat.get("callsign"),
                "platform_type": ptype,
                "latitude": pos.get("lat"),
                "longitude": pos.get("lon"),
                "operational_role": scenario_plat.get("role", "EW"),
                "jamming_active": False,
                "jam_mode": spec.get("jam_mode", "noise"),
                "band": spec.get("band"),
                "frequency_mhz": spec.get("frequency_mhz"),
                "bandwidth_mhz": spec.get("bandwidth_mhz"),
                "coverage_nm": 80,
                "task_role": "",
                "readiness": "standby",
            }
        )
    return ew_rows


def _enrich_commlinks(
    commlink_display: dict[str, Any],
    directory_links: list[Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    freq_by_link = {link.id: link.frequency_mhz for link in directory_links}

    enriched_links = []
    for link in commlink_display.get("links") or []:
        lid = link.get("link_id")
        freq = freq_by_link.get(lid)
        spec = _infer_comm_spec(catalog, {**link, "frequency_mhz": freq})
        enriched_links.append(
            {
                **link,
                "frequency_mhz": freq,
                "bandwidth_mhz": spec.get("bandwidth_mhz"),
                "band": spec.get("band"),
                "emitter_class": "comm",
            }
        )
    return {**commlink_display, "links": enriched_links}


def _build_spectrum(
    comm_links: list[dict[str, Any]],
    emitters: list[dict[str, Any]],
    ew_platforms: list[dict[str, Any]],
) -> dict[str, Any]:
    bands: dict[str, dict[str, Any]] = {}

    def _add_band(key: str, freq: float, bw: float, source: str, affiliation: str, emitter_class: str) -> None:
        rounded = round(freq, 1)
        entry = bands.setdefault(
            str(rounded),
            {
                "frequency_mhz": rounded,
                "bandwidth_mhz": bw,
                "occupants": [],
                "affiliations": set(),
                "classes": set(),
            },
        )
        entry["occupants"].append(source)
        entry["affiliations"].add(affiliation)
        entry["classes"].add(emitter_class)

    for link in comm_links:
        freq = link.get("frequency_mhz")
        if freq:
            _add_band(
                link.get("link_id", "link"),
                float(freq),
                float(link.get("bandwidth_mhz") or 1),
                link.get("link_id", "comm"),
                "friendly",
                "comm",
            )

    for emitter in emitters:
        freq = emitter.get("frequency_mhz")
        if freq:
            _add_band(
                emitter.get("emitter_id", "emitter"),
                float(freq),
                float(emitter.get("bandwidth_mhz") or 10),
                emitter.get("label", emitter.get("emitter_type", "emitter")),
                emitter.get("affiliation", "unknown"),
                emitter.get("emitter_class", "unknown"),
            )

    for jammer in ew_platforms:
        if not jammer.get("jamming_active"):
            continue
        freq = jammer.get("frequency_mhz")
        if freq:
            _add_band(
                jammer.get("platform_id", "jammer"),
                float(freq),
                float(jammer.get("bandwidth_mhz") or 100),
                jammer.get("callsign", jammer.get("platform_id", "jammer")),
                "friendly",
                "jammer",
            )

    rows = []
    for entry in sorted(bands.values(), key=lambda b: b["frequency_mhz"]):
        affs = sorted(entry["affiliations"])
        classes = sorted(entry["classes"])
        contested = len(affs) > 1 or ("jammer" in classes and "comm" in classes)
        rows.append(
            {
                "frequency_mhz": entry["frequency_mhz"],
                "bandwidth_mhz": entry["bandwidth_mhz"],
                "occupant_count": len(entry["occupants"]),
                "occupants": entry["occupants"][:6],
                "affiliations": affs,
                "emitter_classes": classes,
                "contested": contested,
            }
        )

    return {
        "band_count": len(rows),
        "contested_bands": sum(1 for r in rows if r["contested"]),
        "rows": rows,
    }


def build_rf_picture(
    *,
    sim_minutes: float,
    commlink_display: dict[str, Any],
    directory_links: list[Any],
    engine_snapshot: Any | None = None,
    scenario: dict[str, Any] | None = None,
    emso_conflicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    catalog = _load_json_fixture(_EMITTER_CATALOG)
    emcon_doc = _load_json_fixture(_EMCON_AREAS)
    emcon_areas = list(emcon_doc.get("areas") or [])

    commlinks = _enrich_commlinks(commlink_display, directory_links, catalog)
    comm_links = commlinks.get("links") or []

    cues: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    platforms: list[dict[str, Any]] = []
    if engine_snapshot is not None:
        cues = list(getattr(engine_snapshot, "cues", []) or [])
        entities = list(getattr(engine_snapshot, "entities", []) or [])
        platforms = list(getattr(engine_snapshot, "platforms", []) or [])

    emitters = _build_emitters_from_cues(cues, entities, catalog)
    ew_platforms = _build_ew_platforms(scenario or {}, platforms, catalog, sim_minutes)
    spectrum = _build_spectrum(comm_links, emitters, ew_platforms)

    conflicts = detect_rf_conflicts(
        comm_links=comm_links,
        emitters=emitters,
        ew_platforms=ew_platforms,
        emcon_areas=emcon_areas,
        emso_conflicts=emso_conflicts,
    )

    by_type: dict[str, int] = {}
    for c in conflicts:
        by_type[c["conflict_type"]] = by_type.get(c["conflict_type"], 0) + 1

    return {
        "sim_minutes": sim_minutes,
        "commlinks": commlinks,
        "emitters": emitters,
        "ew_platforms": ew_platforms,
        "emcon_areas": emcon_areas,
        "spectrum": spectrum,
        "conflicts": conflicts,
        "deconfliction_summary": {
            "total_conflicts": len(conflicts),
            "high_severity": sum(1 for c in conflicts if c.get("severity") == "high"),
            "by_type": by_type,
            "contested_bands": spectrum.get("contested_bands", 0),
            "active_jammers": sum(1 for p in ew_platforms if p.get("jamming_active")),
            "threat_emitters": sum(1 for e in emitters if e.get("affiliation") == "hostile"),
            "emcon_areas": len(emcon_areas),
        },
    }
