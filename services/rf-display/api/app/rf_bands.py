"""ITU nine-band radio spectrum grouping for RF display summaries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ITU_BANDS = _REPO_ROOT / "fixtures" / "rf-itu-bands-v1.json"

# Default relative power (0–1) by emitter class for channel drill-down when no FSPL available.
_POWER_BY_CLASS: dict[str, float] = {
    "jammer": 1.0,
    "radar": 0.82,
    "comm": 0.55,
    "support": 0.48,
    "unknown": 0.4,
}


def load_itu_bands() -> list[dict[str, Any]]:
    doc = json.loads(_ITU_BANDS.read_text(encoding="utf-8"))
    return list(doc.get("bands") or [])


def band_for_frequency_mhz(freq_mhz: float) -> dict[str, Any] | None:
    for band in load_itu_bands():
        if band["freq_low_mhz"] <= freq_mhz < band["freq_high_mhz"]:
            return band
    return None


def bands_for_asset(freq_low: float, freq_high: float) -> list[dict[str, Any]]:
    """Return ITU bands touched by an asset frequency span."""
    touched: list[dict[str, Any]] = []
    for band in load_itu_bands():
        if freq_high < band["freq_low_mhz"] or freq_low >= band["freq_high_mhz"]:
            continue
        touched.append(band)
    return touched


def _asset_index(columns: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for col in columns:
        col_id = col.get("id", "")
        for asset in col.get("assets") or []:
            key = f"{col_id}:{asset.get('asset_id', '')}"
            index[key] = {**asset, "column": col_id}
    return index


def _power_level(asset: dict[str, Any]) -> float:
    if asset.get("jamming_active"):
        return 1.0
    fspl = asset.get("fspl_at_effective_db")
    if isinstance(fspl, (int, float)):
        return max(0.15, min(1.0, 1.0 + float(fspl) / 40.0))
    emitter_class = str(asset.get("emitter_class") or "unknown")
    return _POWER_BY_CLASS.get(emitter_class, 0.4)


def _interaction_id(overlap: dict[str, Any]) -> str:
    ids = sorted(overlap.get("asset_ids") or [])
    freq = overlap.get("frequency_mhz", 0)
    return f"{overlap.get('conflict_type', 'overlap')}-{freq:.3f}-{'-'.join(ids)}"


def build_spectrum_band_summary(
    spectrum_columns: dict[str, Any],
    *,
    conflicts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Roll up column assets and overlaps into nine ITU band summaries."""
    columns = spectrum_columns.get("columns") or []
    overlap_bands = spectrum_columns.get("overlap_bands") or []
    asset_index = _asset_index(columns)
    conflicts = conflicts or []

    band_rows: list[dict[str, Any]] = []
    for band in load_itu_bands():
        band_id = band["id"]
        assets_in_band: list[dict[str, Any]] = []
        by_column: dict[str, int] = {
            "threat_radars": 0,
            "jammers": 0,
            "comm": 0,
            "support": 0,
        }
        for col in columns:
            col_id = col.get("id", "")
            for asset in col.get("assets") or []:
                low = float(asset.get("freq_low_mhz") or asset.get("frequency_mhz") or 0)
                high = float(asset.get("freq_high_mhz") or low)
                if high < band["freq_low_mhz"] or low >= band["freq_high_mhz"]:
                    continue
                assets_in_band.append({**asset, "column": col_id})
                if col_id in by_column:
                    by_column[col_id] += 1

        band_overlaps = [
            ob
            for ob in overlap_bands
            if band["freq_low_mhz"] <= float(ob.get("frequency_mhz") or 0) < band["freq_high_mhz"]
        ]
        band_conflicts = [
            c
            for c in conflicts
            if band["freq_low_mhz"] <= float(c.get("frequency_mhz") or 0) < band["freq_high_mhz"]
        ]
        conflict_types = sorted({ob.get("conflict_type") for ob in band_overlaps if ob.get("conflict_type")})
        jam_count = sum(1 for ob in band_overlaps if str(ob.get("conflict_type", "")).startswith("jam_"))
        active_low = min((a["freq_low_mhz"] for a in assets_in_band), default=None)
        active_high = max((a["freq_high_mhz"] for a in assets_in_band), default=None)

        band_rows.append(
            {
                "band_id": band_id,
                "number": band["number"],
                "label": band["label"],
                "name": band["name"],
                "freq_range_mhz": [band["freq_low_mhz"], band["freq_high_mhz"]],
                "use_cases": band.get("use_cases", ""),
                "occupant_count": len(assets_in_band),
                "by_column": by_column,
                "interaction_count": len(band_overlaps),
                "jam_interaction_count": jam_count,
                "conflict_count": len(band_conflicts),
                "conflict_types": conflict_types,
                "contested": jam_count > 0 or len(band_conflicts) > 0,
                "active_span_mhz": [active_low, active_high] if active_low is not None else None,
                "asset_ids": [a.get("asset_id") for a in assets_in_band],
            }
        )

    interactions: list[dict[str, Any]] = []
    for overlap in overlap_bands:
        freq = float(overlap.get("frequency_mhz") or 0)
        band = band_for_frequency_mhz(freq)
        endpoints = overlap.get("endpoints") or []
        devices: list[dict[str, Any]] = []
        for ep in endpoints:
            key = f"{ep.get('column')}:{ep.get('asset_id')}"
            asset = asset_index.get(key)
            if not asset:
                continue
            span_low = max(float(asset.get("freq_low_mhz") or freq), overlap.get("freq_low_mhz", freq))
            span_high = min(float(asset.get("freq_high_mhz") or freq), overlap.get("freq_high_mhz", freq))
            overlap_width = max(span_high - span_low, 0.001)
            devices.append(
                {
                    "asset_id": asset.get("asset_id"),
                    "column": asset.get("column"),
                    "label": asset.get("label"),
                    "emitter_class": asset.get("emitter_class"),
                    "affiliation": asset.get("affiliation"),
                    "frequency_mhz": asset.get("frequency_mhz"),
                    "bandwidth_mhz": asset.get("bandwidth_mhz"),
                    "channel_low_mhz": span_low,
                    "channel_high_mhz": span_high,
                    "channel_width_mhz": overlap_width,
                    "power_level": round(_power_level(asset), 3),
                    "jamming_active": bool(asset.get("jamming_active")),
                    "jammed": bool(asset.get("jammed_by")),
                }
            )

        interactions.append(
            {
                "interaction_id": _interaction_id(overlap),
                "band_id": band["id"] if band else None,
                "band_label": band["label"] if band else None,
                "frequency_mhz": freq,
                "freq_low_mhz": overlap.get("freq_low_mhz"),
                "freq_high_mhz": overlap.get("freq_high_mhz"),
                "conflict_type": overlap.get("conflict_type"),
                "severity": overlap.get("severity"),
                "columns": overlap.get("columns") or [],
                "asset_ids": overlap.get("asset_ids") or [],
                "devices": devices,
            }
        )

    return {
        "band_count": len(band_rows),
        "bands": band_rows,
        "interactions": interactions,
        "active_band_count": sum(1 for b in band_rows if b["occupant_count"] > 0),
        "contested_band_count": sum(1 for b in band_rows if b["contested"]),
    }


def build_interaction_drilldown(interaction: dict[str, Any]) -> dict[str, Any]:
    """Normalize one interaction for horizontal channel drill-down UI."""
    devices = list(interaction.get("devices") or [])
    if not devices:
        return interaction
    max_power = max((d.get("power_level") or 0.1) for d in devices) or 1.0
    channel_span = float(interaction.get("freq_high_mhz") or 0) - float(interaction.get("freq_low_mhz") or 0)
    if channel_span <= 0:
        channel_span = max((d.get("channel_width_mhz") or 1) for d in devices)

    normalized: list[dict[str, Any]] = []
    for device in devices:
        width = float(device.get("channel_width_mhz") or 1)
        low = float(device.get("channel_low_mhz") or interaction.get("freq_low_mhz") or 0)
        power = float(device.get("power_level") or 0.4)
        normalized.append(
            {
                **device,
                "channel_left_pct": round((low - float(interaction.get("freq_low_mhz") or low)) / channel_span * 100, 2)
                if channel_span
                else 0,
                "channel_width_pct": round(width / channel_span * 100, 2) if channel_span else 100,
                "power_pct": round(power / max_power * 100, 1),
            }
        )

    return {**interaction, "channel_span_mhz": channel_span, "devices": normalized}
