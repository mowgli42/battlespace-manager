"""Threat registry, BDA suppression, opzone applicability, and jam stand-down for RF picture."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.rf_bands import band_for_frequency_mhz
from app.rf_deconfliction import bands_overlap

_REPO_ROOT = Path(__file__).resolve().parents[4]
_OPZONES = _REPO_ROOT / "fixtures" / "opzones-v1.json"
_EMITTER_CATALOG = _REPO_ROOT / "fixtures" / "rf-emitter-catalog-v1.json"

_DEFAULT_SUPPRESS = frozenset({"destroyed", "damaged"})


def _suppress_statuses() -> frozenset[str]:
    raw = os.getenv("RF_BDA_SUPPRESS_STATUSES", "destroyed,damaged").strip().lower()
    if not raw:
        return _DEFAULT_SUPPRESS
    return frozenset(s.strip() for s in raw.split(",") if s.strip())


def load_opzone_catalog() -> list[dict[str, Any]]:
    if not _OPZONES.is_file():
        return []
    return list(json.loads(_OPZONES.read_text(encoding="utf-8")).get("opzones") or [])


def opzone_to_geo_filter(opzone: dict[str, Any]) -> dict[str, Any]:
    """Convert catalog opzone to geo_filter payload."""
    return {
        "type": opzone.get("type", "polygon"),
        "active": True,
        "label": opzone.get("label", opzone.get("id", "")),
        "opzone_id": opzone.get("id"),
        "geometry": dict(opzone.get("geometry") or {}),
        "include_non_geo": False,
    }


def _load_catalog() -> dict[str, Any]:
    if not _EMITTER_CATALOG.is_file():
        return {}
    return json.loads(_EMITTER_CATALOG.read_text(encoding="utf-8"))


def _catalog_freq(platform_type: str, catalog: dict[str, Any]) -> tuple[float | None, float | None, str | None]:
    emitters = catalog.get("emitters") or {}
    spec = emitters.get(platform_type)
    if not spec:
        for key, val in emitters.items():
            if platform_type.upper() in key.upper() or key.upper() in platform_type.upper():
                spec = val
                break
    if not spec:
        return None, None, None
    return (
        spec.get("frequency_mhz"),
        spec.get("bandwidth_mhz"),
        spec.get("band"),
    )


def _phase_for_entity(entity_id: str, kill_chains: list[dict[str, Any]]) -> str | None:
    for kc in kill_chains:
        if kc.get("target_entity_id") == entity_id:
            return kc.get("phase")
    return None


def _bda_for_entity(entity_id: str, entity_meta: dict[str, dict[str, Any]]) -> str | None:
    return entity_meta.get(entity_id, {}).get("bda_status")


def _effective_status(
    *,
    bda_status: str | None,
    in_opzone: bool,
    opzone_active: bool,
) -> str:
    if bda_status and bda_status.lower() in _suppress_statuses():
        return "suppressed"
    if opzone_active and not in_opzone:
        return "out_of_opzone"
    return "active"


def _in_opzone(lat: float | None, lon: float | None, geo_filter: dict[str, Any] | None) -> bool:
    if not geo_filter or not geo_filter.get("active"):
        return True
    if lat is None or lon is None:
        return bool(geo_filter.get("include_non_geo"))
    from app.geo_filter import geo_filter_matches

    return geo_filter_matches(float(lat), float(lon), geo_filter)


def apply_emitter_overrides(
    emitters: list[dict[str, Any]],
    harness_overrides: list[dict[str, Any]] | None,
) -> None:
    """Apply harness frequency/label overrides onto emitter rows in place."""
    by_id = {row["entity_id"]: row for row in (harness_overrides or []) if row.get("entity_id")}
    for em in emitters:
        eid = em.get("target_entity_id") or em.get("emitter_id", "")
        override = by_id.get(eid, {})
        if override.get("frequency_mhz") is not None:
            freq = float(override["frequency_mhz"])
            em["frequency_mhz"] = freq
            band = band_for_frequency_mhz(freq)
            if band:
                em["band"] = band["label"]
        if override.get("bandwidth_mhz") is not None:
            em["bandwidth_mhz"] = float(override["bandwidth_mhz"])
        if override.get("label"):
            em["label"] = override["label"]


def build_threat_registry(
    *,
    emitters: list[dict[str, Any]],
    engine_snapshot: Any | None = None,
    harness_overrides: list[dict[str, Any]] | None = None,
    geo_filter: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build per-threat rows with frequency, F2T2EA phase, BDA, and opzone applicability."""
    catalog = _load_catalog()
    kill_chains: list[dict[str, Any]] = []
    entity_meta: dict[str, dict[str, Any]] = {}
    if engine_snapshot is not None:
        kill_chains = list(getattr(engine_snapshot, "kill_chains", []) or [])
        entity_meta = dict(getattr(engine_snapshot, "entity_meta", {}) or {})

    override_by_id = {row["entity_id"]: row for row in (harness_overrides or []) if row.get("entity_id")}
    opzone_active = bool(geo_filter and geo_filter.get("active"))

    registry: list[dict[str, Any]] = []
    seen: set[str] = set()

    for em in emitters:
        eid = em.get("target_entity_id") or em.get("emitter_id", "")
        if not eid or eid in seen:
            continue
        seen.add(eid)
        override = override_by_id.get(eid, {})
        freq = float(override.get("frequency_mhz") or em.get("frequency_mhz") or 0)
        band = band_for_frequency_mhz(freq) if freq else None
        bda = override.get("bda_status") or _bda_for_entity(eid, entity_meta)
        phase = override.get("f2t2ea_phase") or _phase_for_entity(eid, kill_chains)
        lat = override.get("latitude", em.get("latitude"))
        lon = override.get("longitude", em.get("longitude"))
        in_zone = _in_opzone(lat, lon, geo_filter)
        status = _effective_status(bda_status=bda, in_opzone=in_zone, opzone_active=opzone_active)

        registry.append(
            {
                "entity_id": eid,
                "label": override.get("label") or em.get("label", eid),
                "platform_type": override.get("platform_type") or em.get("emitter_type", ""),
                "frequency_mhz": freq,
                "bandwidth_mhz": em.get("bandwidth_mhz"),
                "band": em.get("band") or (band["label"] if band else None),
                "band_id": band["id"] if band else None,
                "f2t2ea_phase": phase,
                "bda_status": bda,
                "effective_status": status,
                "latitude": lat,
                "longitude": lon,
                "in_opzone": in_zone,
            }
        )

    for eid, override in override_by_id.items():
        if eid in seen:
            continue
        freq = float(override.get("frequency_mhz") or 0)
        band = band_for_frequency_mhz(freq) if freq else None
        bda = override.get("bda_status")
        lat = override.get("latitude")
        lon = override.get("longitude")
        in_zone = _in_opzone(lat, lon, geo_filter)
        status = _effective_status(bda_status=bda, in_opzone=in_zone, opzone_active=opzone_active)
        registry.append(
            {
                "entity_id": eid,
                "label": override.get("label", eid),
                "platform_type": override.get("platform_type", ""),
                "frequency_mhz": freq,
                "bandwidth_mhz": override.get("bandwidth_mhz"),
                "band": override.get("band") or (band["label"] if band else None),
                "band_id": band["id"] if band else None,
                "f2t2ea_phase": override.get("f2t2ea_phase"),
                "bda_status": bda,
                "effective_status": status,
                "latitude": lat,
                "longitude": lon,
                "in_opzone": in_zone,
            }
        )

    registry.sort(key=lambda r: (r.get("band_id") or "", r.get("label") or ""))
    return registry


def filter_emitters_by_threat_registry(
    emitters: list[dict[str, Any]],
    registry: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (visible_emitters, suppressed_emitters)."""
    by_target = {r["entity_id"]: r for r in registry}
    visible: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for em in emitters:
        eid = em.get("target_entity_id") or em.get("emitter_id", "")
        row = by_target.get(eid)
        if row and row.get("effective_status") != "active":
            suppressed.append({**em, **row})
            continue
        visible.append(em)
    return visible, suppressed


def apply_jam_standdown(
    ew_platforms: list[dict[str, Any]],
    active_emitters: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Stand down jammers with no overlapping active threat emitters."""
    updated: list[dict[str, Any]] = []
    for jam in ew_platforms:
        row = dict(jam)
        if not row.get("jamming_active"):
            updated.append(row)
            continue
        jam_freq = float(row.get("frequency_mhz") or 0)
        jam_bw = float(row.get("bandwidth_mhz") or 100)
        has_target = any(
            bands_overlap(
                jam_freq,
                jam_bw,
                float(em.get("frequency_mhz") or 0),
                float(em.get("bandwidth_mhz") or 10),
            )
            for em in active_emitters
            if em.get("emitter_class") == "radar" or "RADAR" in str(em.get("emitter_type", "")).upper()
        )
        if not has_target:
            row["jamming_active"] = False
            row["jam_standdown_reason"] = "no_active_threats_in_band"
        updated.append(row)
    return updated


def threat_summary(registry: list[dict[str, Any]]) -> dict[str, Any]:
    active = [r for r in registry if r.get("effective_status") == "active"]
    suppressed = [r for r in registry if r.get("effective_status") == "suppressed"]
    out_of_zone = [r for r in registry if r.get("effective_status") == "out_of_opzone"]
    by_band: dict[str, int] = {}
    for r in active:
        bid = r.get("band_id") or "unknown"
        by_band[bid] = by_band.get(bid, 0) + 1
    return {
        "total": len(registry),
        "active": len(active),
        "suppressed": len(suppressed),
        "out_of_opzone": len(out_of_zone),
        "active_by_band": by_band,
    }
