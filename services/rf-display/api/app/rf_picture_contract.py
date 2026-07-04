"""RF operator picture JSON contract for /api/picture and SSE stream."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.rf_deconfliction import bands_overlap, detect_rf_conflicts
from app.rf_propagation import jam_effective_coverage_nm

RF_PICTURE_REQUIRED_KEYS: frozenset[str] = frozenset(
    {
        "sim_minutes",
        "commlinks",
        "emitters",
        "ew_platforms",
        "emcon_areas",
        "spectrum",
        "spectrum_columns",
        "support_assets",
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
    "spectrum_columns": dict,
    "support_assets": list,
    "conflicts": list,
    "deconfliction_summary": dict,
}

_REPO_ROOT = Path(__file__).resolve().parents[4]
_EMITTER_CATALOG = _REPO_ROOT / "fixtures" / "rf-emitter-catalog-v1.json"
_EMCON_AREAS = _REPO_ROOT / "fixtures" / "rf-emcon-areas-v1.json"
_JRFL = _REPO_ROOT / "fixtures" / "rf-jrfl-v1.json"

_RADAR_KEYWORDS = ("RADAR", "SAM", "FIRE_CONTROL", "ACQUISITION")
_EW_CAPABILITIES = frozenset({"EW_SUPPORT", "SEAD"})
_SUPPORT_PLATFORM_TYPES = {
    "E-3": "E-3_AWACS",
    "AWACS": "E-3_AWACS",
    "E-2": "E-2_HAWKEYE",
}
_SUPPORT_SUBSYSTEM_KEYS = ("datalink", "radar", "iff", "tacan", "gps")


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
        jamming_active = task_role in ("SEAD", "EW_SUPPORT")
        alt_ft = float(
            plat.get("altitude_feet")
            or (scenario_plat or {}).get("initialPosition", {}).get("altitudeFeet", 35000)
        )
        freq = float(spec.get("frequency_mhz") or 9500)
        prop = jam_effective_coverage_nm(frequency_mhz=freq, altitude_feet=alt_ft)
        ew_rows.append(
            {
                "platform_id": pid,
                "callsign": plat.get("callsign"),
                "platform_type": ptype,
                "latitude": plat.get("latitude"),
                "longitude": plat.get("longitude"),
                "altitude_feet": alt_ft,
                "operational_role": plat.get("operational_role") or (scenario_plat or {}).get("role", "EW"),
                "jamming_active": jamming_active,
                "jam_mode": spec.get("jam_mode", "noise"),
                "band": spec.get("band"),
                "frequency_mhz": spec.get("frequency_mhz"),
                "bandwidth_mhz": spec.get("bandwidth_mhz"),
                "coverage_nm": prop["effective_coverage_nm"],
                "nominal_coverage_nm": prop["nominal_coverage_nm"],
                "terrain_mask_factor": prop["terrain_mask_factor"],
                "fspl_at_effective_db": prop["fspl_at_effective_db"],
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
        alt_ft = float(pos.get("altitudeFeet", 35000))
        freq = float(spec.get("frequency_mhz") or 9500)
        prop = jam_effective_coverage_nm(frequency_mhz=freq, altitude_feet=alt_ft)
        ew_rows.append(
            {
                "platform_id": pid,
                "callsign": scenario_plat.get("callsign"),
                "platform_type": ptype,
                "latitude": pos.get("lat"),
                "longitude": pos.get("lon"),
                "altitude_feet": alt_ft,
                "operational_role": scenario_plat.get("role", "EW"),
                "jamming_active": False,
                "jam_mode": spec.get("jam_mode", "noise"),
                "band": spec.get("band"),
                "frequency_mhz": spec.get("frequency_mhz"),
                "bandwidth_mhz": spec.get("bandwidth_mhz"),
                "coverage_nm": prop["effective_coverage_nm"],
                "nominal_coverage_nm": prop["nominal_coverage_nm"],
                "terrain_mask_factor": prop["terrain_mask_factor"],
                "fspl_at_effective_db": prop["fspl_at_effective_db"],
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
    jrfl_entries: list[dict[str, Any]] | None = None,
    spectrum_analytics: dict[str, Any] | None = None,
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

    jrfl_by_freq = {round(float(e.get("frequency_mhz", 0)), 1): e for e in (jrfl_entries or []) if e.get("frequency_mhz")}

    rows = []
    for entry in sorted(bands.values(), key=lambda b: b["frequency_mhz"]):
        affs = sorted(entry["affiliations"])
        classes = sorted(entry["classes"])
        contested = len(affs) > 1 or ("jammer" in classes and "comm" in classes)
        jrfl = jrfl_by_freq.get(entry["frequency_mhz"])
        rows.append(
            {
                "frequency_mhz": entry["frequency_mhz"],
                "bandwidth_mhz": entry["bandwidth_mhz"],
                "occupant_count": len(entry["occupants"]),
                "occupants": entry["occupants"][:6],
                "affiliations": affs,
                "emitter_classes": classes,
                "contested": contested,
                "jrfl_protected": jrfl is not None,
                "jrfl_label": jrfl.get("label") if jrfl else None,
                "jrfl_restriction": jrfl.get("restriction") if jrfl else None,
            }
        )

    analytics = spectrum_analytics or {}
    return {
        "band_count": len(rows),
        "contested_bands": sum(1 for r in rows if r["contested"]),
        "jrfl_protected_bands": sum(1 for r in rows if r["jrfl_protected"]),
        "utilization_pct": analytics.get("utilization_pct"),
        "rows": rows,
    }


def _asset_freq_bounds(freq: float, bw: float) -> tuple[float, float]:
    half = float(bw or 1) / 2
    return freq - half, freq + half


def _build_support_assets(
    scenario: dict[str, Any],
    platforms: list[dict[str, Any]],
    catalog: dict[str, Any],
    highlight_entity_id: str | None = None,
) -> list[dict[str, Any]]:
    """Friendly GPS, radars, and platform RF systems for the support column."""
    assets: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(
        asset_id: str,
        *,
        label: str,
        support_kind: str,
        emitter_class: str,
        spec: dict[str, Any],
        platform_id: str | None = None,
        callsign: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        subsystem: str | None = None,
        status: str = "active",
    ) -> None:
        if asset_id in seen:
            return
        freq = spec.get("frequency_mhz")
        if not freq:
            return
        seen.add(asset_id)
        bw = float(spec.get("bandwidth_mhz") or 1)
        freq_f = float(freq)
        low, high = _asset_freq_bounds(freq_f, bw)
        assets.append(
            {
                "asset_id": asset_id,
                "label": label,
                "support_kind": support_kind,
                "emitter_class": emitter_class,
                "affiliation": "friendly",
                "band": spec.get("band"),
                "frequency_mhz": freq_f,
                "bandwidth_mhz": bw,
                "freq_low_mhz": low,
                "freq_high_mhz": high,
                "platform_id": platform_id,
                "callsign": callsign,
                "latitude": latitude,
                "longitude": longitude,
                "subsystem": subsystem,
                "status": status,
                "highlighted": bool(
                    highlight_entity_id
                    and (asset_id == highlight_entity_id or platform_id == highlight_entity_id)
                ),
            }
        )

    for gps_key, kind in (("GPS_L1", "gps"), ("GPS_L2", "gps")):
        spec = _catalog_entry(catalog, gps_key)
        if spec:
            _add(
                gps_key,
                label=spec.get("label", gps_key),
                support_kind=kind,
                emitter_class=spec.get("emitter_class", "pnt"),
                spec=spec,
            )

    coalition = {p["platformId"]: p for p in (scenario.get("coalitionPlatforms") or []) if p.get("platformId")}
    plat_by_id = {p.get("platform_id"): p for p in platforms if p.get("platform_id")}

    for pid, scenario_plat in coalition.items():
        ptype = (scenario_plat.get("type") or "").upper()
        role = (scenario_plat.get("role") or "").upper()
        plat = plat_by_id.get(pid, {})
        lat = plat.get("latitude") or (scenario_plat.get("initialPosition") or {}).get("lat")
        lon = plat.get("longitude") or (scenario_plat.get("initialPosition") or {}).get("lon")
        if lat is None and scenario_plat.get("orbit"):
            lat = scenario_plat["orbit"].get("lat")
            lon = scenario_plat["orbit"].get("lon")
        callsign = plat.get("callsign") or scenario_plat.get("callsign")

        catalog_key = _SUPPORT_PLATFORM_TYPES.get(ptype) or _SUPPORT_PLATFORM_TYPES.get(role)
        if catalog_key or "AWACS" in role or "E-3" in ptype:
            spec = _catalog_entry(catalog, catalog_key or "E-3_AWACS")
            _add(
                f"{pid}-radar",
                label=f"{callsign or pid} · {spec.get('label', 'Radar')}",
                support_kind="friendly_radar",
                emitter_class="radar",
                spec=spec,
                platform_id=pid,
                callsign=callsign,
                latitude=lat,
                longitude=lon,
                subsystem="radar",
            )

        subs = plat.get("subsystems") or {}
        for sub_key, sub_status in subs.items():
            sub_lower = sub_key.lower()
            if not any(k in sub_lower for k in _SUPPORT_SUBSYSTEM_KEYS):
                continue
            if str(sub_status).upper() in ("OFFLINE", "UNAVAILABLE", "EMPTY"):
                continue
            if "datalink" in sub_lower or "link" in sub_lower:
                spec = _catalog_entry(catalog, "LINK16")
                _add(
                    f"{pid}-datalink",
                    label=f"{callsign or pid} · Link-16",
                    support_kind="datalink",
                    emitter_class="datalink",
                    spec=spec,
                    platform_id=pid,
                    callsign=callsign,
                    latitude=lat,
                    longitude=lon,
                    subsystem=sub_key,
                    status=str(sub_status).lower(),
                )
            elif "satcom" in sub_lower:
                spec = _catalog_entry(catalog, "SATCOM_L" if "lband" in sub_lower or "iridium" in sub_lower else "SATCOM_KA")
                _add(
                    f"{pid}-{sub_key}",
                    label=f"{callsign or pid} · {spec.get('label', 'SATCOM')}",
                    support_kind="satcom",
                    emitter_class="comm",
                    spec=spec,
                    platform_id=pid,
                    callsign=callsign,
                    latitude=lat,
                    longitude=lon,
                    subsystem=sub_key,
                    status=str(sub_status).lower(),
                )

    for plat in platforms:
        pid = plat.get("platform_id", "")
        if pid in coalition or not pid:
            continue
        role = (plat.get("operational_role") or "").upper()
        ptype = (plat.get("platform_type") or "").upper()
        if "EW" in role:
            continue
        if "AWACS" in role or "E-3" in ptype:
            spec = _catalog_entry(catalog, "E-3_AWACS")
            _add(
                f"{pid}-radar",
                label=f"{plat.get('callsign', pid)} · AWACS",
                support_kind="friendly_radar",
                emitter_class="radar",
                spec=spec,
                platform_id=pid,
                callsign=plat.get("callsign"),
                latitude=plat.get("latitude"),
                longitude=plat.get("longitude"),
                subsystem="radar",
            )

    assets.sort(key=lambda a: (a.get("frequency_mhz") or 0, a.get("label") or ""))
    return assets


def _column_asset(
    *,
    asset_id: str,
    column: str,
    label: str,
    emitter_class: str,
    affiliation: str,
    band: str | None,
    frequency_mhz: float,
    bandwidth_mhz: float,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    low, high = _asset_freq_bounds(frequency_mhz, bandwidth_mhz)
    row = {
        "asset_id": asset_id,
        "column": column,
        "label": label,
        "emitter_class": emitter_class,
        "affiliation": affiliation,
        "band": band,
        "frequency_mhz": frequency_mhz,
        "bandwidth_mhz": bandwidth_mhz,
        "freq_low_mhz": low,
        "freq_high_mhz": high,
        "overlaps_with": [],
        "jammed_by": [],
        "jamming_targets": [],
    }
    if extra:
        row.update(extra)
    return row


def _append_overlap(
    source: dict[str, Any],
    *,
    target_column: str,
    target_asset_id: str,
    conflict_type: str,
    severity: str = "medium",
) -> None:
    ref = {
        "column": target_column,
        "asset_id": target_asset_id,
        "conflict_type": conflict_type,
        "severity": severity,
    }
    overlaps = source.setdefault("overlaps_with", [])
    if not any(o["asset_id"] == target_asset_id and o["column"] == target_column for o in overlaps):
        overlaps.append(ref)


def _build_spectrum_columns(
    *,
    threat_radars: list[dict[str, Any]],
    jammers: list[dict[str, Any]],
    comm_links: list[dict[str, Any]],
    support_assets: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    columns: dict[str, list[dict[str, Any]]] = {
        "threat_radars": [],
        "jammers": [],
        "comm": [],
        "support": [],
    }

    for em in threat_radars:
        freq = em.get("frequency_mhz")
        if not freq:
            continue
        columns["threat_radars"].append(
            _column_asset(
                asset_id=em.get("emitter_id", ""),
                column="threat_radars",
                label=em.get("label", em.get("emitter_type", "Radar")),
                emitter_class=em.get("emitter_class", "radar"),
                affiliation=em.get("affiliation", "hostile"),
                band=em.get("band"),
                frequency_mhz=float(freq),
                bandwidth_mhz=float(em.get("bandwidth_mhz") or 10),
                extra={
                    "highlighted": em.get("highlighted", False),
                    "target_entity_id": em.get("target_entity_id"),
                    "latitude": em.get("latitude"),
                    "longitude": em.get("longitude"),
                },
            )
        )

    for jam in jammers:
        freq = jam.get("frequency_mhz")
        if not freq:
            continue
        columns["jammers"].append(
            _column_asset(
                asset_id=jam.get("platform_id", ""),
                column="jammers",
                label=jam.get("callsign") or jam.get("platform_id", "Jammer"),
                emitter_class="jammer",
                affiliation="friendly",
                band=jam.get("band"),
                frequency_mhz=float(freq),
                bandwidth_mhz=float(jam.get("bandwidth_mhz") or 100),
                extra={
                    "jamming_active": jam.get("jamming_active", False),
                    "coverage_nm": jam.get("coverage_nm"),
                    "task_role": jam.get("task_role"),
                    "latitude": jam.get("latitude"),
                    "longitude": jam.get("longitude"),
                },
            )
        )

    for link in comm_links:
        freq = link.get("frequency_mhz")
        if not freq:
            continue
        columns["comm"].append(
            _column_asset(
                asset_id=link.get("link_id", ""),
                column="comm",
                label=link.get("link_id", "Comm"),
                emitter_class="comm",
                affiliation="friendly",
                band=link.get("band"),
                frequency_mhz=float(freq),
                bandwidth_mhz=float(link.get("bandwidth_mhz") or 1),
                extra={
                    "type": link.get("type"),
                    "subtype": link.get("subtype"),
                    "status": link.get("status"),
                    "is_unavailable": link.get("is_unavailable"),
                },
            )
        )

    for asset in support_assets:
        freq = asset.get("frequency_mhz")
        if not freq:
            continue
        columns["support"].append(
            _column_asset(
                asset_id=asset.get("asset_id", ""),
                column="support",
                label=asset.get("label", "Support"),
                emitter_class=asset.get("emitter_class", "support"),
                affiliation="friendly",
                band=asset.get("band"),
                frequency_mhz=float(freq),
                bandwidth_mhz=float(asset.get("bandwidth_mhz") or 1),
                extra={
                    "support_kind": asset.get("support_kind"),
                    "platform_id": asset.get("platform_id"),
                    "callsign": asset.get("callsign"),
                    "subsystem": asset.get("subsystem"),
                    "highlighted": asset.get("highlighted", False),
                    "latitude": asset.get("latitude"),
                    "longitude": asset.get("longitude"),
                },
            )
        )

    conflict_by_pair: dict[tuple[str, str], str] = {}
    for c in conflicts:
        ids = c.get("involved_ids") or []
        if len(ids) < 2:
            continue
        conflict_by_pair[(ids[0], ids[1])] = c["conflict_type"]
        conflict_by_pair[(ids[1], ids[0])] = c["conflict_type"]

    col_pairs = [
        ("jammers", "comm", "jam_comm", "high"),
        ("jammers", "threat_radars", "jam_radar", "medium"),
        ("jammers", "support", "jam_support", "high"),
        ("threat_radars", "comm", "band_overlap", "low"),
        ("threat_radars", "support", "band_overlap", "low"),
        ("comm", "support", "band_overlap", "medium"),
    ]

    overlap_bands: list[dict[str, Any]] = []
    for col_a, col_b, default_type, default_sev in col_pairs:
        for asset_a in columns[col_a]:
            for asset_b in columns[col_b]:
                if asset_a["asset_id"] == asset_b["asset_id"]:
                    continue
                if not bands_overlap(
                    asset_a["frequency_mhz"],
                    asset_a["bandwidth_mhz"],
                    asset_b["frequency_mhz"],
                    asset_b["bandwidth_mhz"],
                ):
                    continue
                ctype = conflict_by_pair.get((asset_a["asset_id"], asset_b["asset_id"]), default_type)
                sev = "high" if ctype in ("jam_comm", "jam_support", "jrfl_violation") else default_sev
                _append_overlap(
                    asset_a,
                    target_column=col_b,
                    target_asset_id=asset_b["asset_id"],
                    conflict_type=ctype,
                    severity=sev,
                )
                _append_overlap(
                    asset_b,
                    target_column=col_a,
                    target_asset_id=asset_a["asset_id"],
                    conflict_type=ctype,
                    severity=sev,
                )
                if col_a == "jammers" and asset_a.get("jamming_active"):
                    asset_a.setdefault("jamming_targets", []).append(
                        {"column": col_b, "asset_id": asset_b["asset_id"], "conflict_type": ctype}
                    )
                    asset_b.setdefault("jammed_by", []).append(
                        {"column": col_a, "asset_id": asset_a["asset_id"], "conflict_type": ctype}
                    )
                overlap_bands.append(
                    {
                        "frequency_mhz": (asset_a["frequency_mhz"] + asset_b["frequency_mhz"]) / 2,
                        "freq_low_mhz": max(asset_a["freq_low_mhz"], asset_b["freq_low_mhz"]),
                        "freq_high_mhz": min(asset_a["freq_high_mhz"], asset_b["freq_high_mhz"]),
                        "columns": sorted({col_a, col_b}),
                        "asset_ids": [asset_a["asset_id"], asset_b["asset_id"]],
                        "conflict_type": ctype,
                        "severity": sev,
                    }
                )

    all_assets = [a for assets in columns.values() for a in assets]
    if all_assets:
        freq_min = min(a["freq_low_mhz"] for a in all_assets)
        freq_max = max(a["freq_high_mhz"] for a in all_assets)
        pad = max((freq_max - freq_min) * 0.05, 50)
        freq_range = [max(0, freq_min - pad), freq_max + pad]
    else:
        freq_range = [1, 15000]

    for asset in all_assets:
        span = freq_range[1] - freq_range[0]
        low, high = asset["freq_low_mhz"], asset["freq_high_mhz"]
        asset["position_pct"] = round((asset["frequency_mhz"] - freq_range[0]) / span * 100, 2)
        asset["height_pct"] = round(max(2, (high - low) / span * 100), 2)

    overlap_bands.sort(key=lambda b: b["frequency_mhz"])

    return {
        "freq_range_mhz": freq_range,
        "columns": [
            {"id": "threat_radars", "label": "Radar Threats", "assets": columns["threat_radars"]},
            {"id": "jammers", "label": "Jammers", "assets": columns["jammers"]},
            {"id": "comm", "label": "Comm", "assets": columns["comm"]},
            {
                "id": "support",
                "label": "Support",
                "subtitle": "GPS · Friendly radars · RF systems",
                "assets": columns["support"],
            },
        ],
        "overlap_bands": overlap_bands,
        "overlap_count": len(overlap_bands),
        "jam_overlap_count": sum(1 for b in overlap_bands if b["conflict_type"].startswith("jam_")),
    }


def build_rf_picture(
    *,
    sim_minutes: float,
    commlink_display: dict[str, Any],
    directory_links: list[Any],
    engine_snapshot: Any | None = None,
    scenario: dict[str, Any] | None = None,
    emso_conflicts: list[dict[str, Any]] | None = None,
    spectrum_analytics: dict[str, Any] | None = None,
    highlight_entity_id: str | None = None,
    bus_connected: bool = False,
) -> dict[str, Any]:
    catalog = _load_json_fixture(_EMITTER_CATALOG)
    emcon_doc = _load_json_fixture(_EMCON_AREAS)
    jrfl_doc = _load_json_fixture(_JRFL)
    emcon_areas = list(emcon_doc.get("areas") or [])
    jrfl_entries = list(jrfl_doc.get("entries") or [])
    ea_authority = jrfl_doc.get("ea_authority") or {}

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
    for em in emitters:
        em["highlighted"] = bool(
            highlight_entity_id
            and (
                em.get("target_entity_id") == highlight_entity_id
                or em.get("emitter_id") == highlight_entity_id
            )
        )
    ew_platforms = _build_ew_platforms(scenario or {}, platforms, catalog, sim_minutes)
    support_assets = _build_support_assets(scenario or {}, platforms, catalog, highlight_entity_id)
    spectrum = _build_spectrum(comm_links, emitters, ew_platforms, jrfl_entries, spectrum_analytics)

    conflicts = detect_rf_conflicts(
        comm_links=comm_links,
        emitters=emitters,
        ew_platforms=ew_platforms,
        emcon_areas=emcon_areas,
        emso_conflicts=emso_conflicts,
        jrfl_entries=jrfl_entries,
        ea_authority=ea_authority,
        support_assets=support_assets,
    )

    threat_radars = [e for e in emitters if e.get("emitter_class") == "radar"]
    spectrum_columns = _build_spectrum_columns(
        threat_radars=threat_radars,
        jammers=ew_platforms,
        comm_links=comm_links,
        support_assets=support_assets,
        conflicts=conflicts,
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
        "jrfl": {"entries": jrfl_entries, "ea_authority": ea_authority},
        "highlight_entity_id": highlight_entity_id,
        "bus_connected": bus_connected,
        "spectrum": spectrum,
        "spectrum_columns": spectrum_columns,
        "support_assets": support_assets,
        "conflicts": conflicts,
        "deconfliction_summary": {
            "total_conflicts": len(conflicts),
            "high_severity": sum(1 for c in conflicts if c.get("severity") == "high"),
            "by_type": by_type,
            "contested_bands": spectrum.get("contested_bands", 0),
            "jrfl_protected_bands": spectrum.get("jrfl_protected_bands", 0),
            "active_jammers": sum(1 for p in ew_platforms if p.get("jamming_active")),
            "threat_emitters": sum(1 for e in emitters if e.get("affiliation") == "hostile"),
            "support_assets": len(support_assets),
            "spectrum_overlaps": spectrum_columns.get("overlap_count", 0),
            "jam_overlaps": spectrum_columns.get("jam_overlap_count", 0),
            "emcon_areas": len(emcon_areas),
            "highlight_entity_id": highlight_entity_id,
        },
    }
