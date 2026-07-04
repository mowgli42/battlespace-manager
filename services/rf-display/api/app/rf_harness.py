"""Build deterministic RF picture from harness fixture (no Gulf War engine)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.geo_filter import apply_geo_filter
from app.omy_bridge import build_commlink_display, load_omy_module
from app.rf_picture_contract import assert_rf_picture_contract, build_rf_picture

_REPO_ROOT = Path(__file__).resolve().parents[4]
_HARNESS_SCENARIO = _REPO_ROOT / "fixtures" / "rf-harness-scenario-v1.json"
_DIRECTORY_XML = _REPO_ROOT / "fixtures" / "commlink-directory-v1.1.xml"

RF_FEATURE_CHECKS: list[tuple[str, str]] = [
    ("four_spectrum_columns", "spectrum_columns has 4 columns"),
    ("threat_radar_assets", "threat_radars column has assets"),
    ("jammer_assets", "jammers column has assets"),
    ("comm_assets", "comm column has assets"),
    ("support_assets", "support column has assets"),
    ("gps_support", "support includes GPS L1"),
    ("jrfl_entries", "jrfl entries present"),
    ("emcon_areas", "emcon areas present"),
    ("deconfliction_summary", "deconfliction_summary populated"),
    ("spectrum_rows", "spectrum occupancy rows"),
    ("overlap_graph", "spectrum_columns overlap_bands list"),
    ("geo_locations", "emitters have lat/lon for map filter"),
]


def load_harness_document() -> dict[str, Any]:
    return json.loads(_HARNESS_SCENARIO.read_text(encoding="utf-8"))


def harness_snapshot(doc: dict[str, Any] | None = None) -> SimpleNamespace:
    data = doc or load_harness_document()
    return SimpleNamespace(
        sim_minutes=float(data.get("sim_minutes", 0)),
        cues=list(data.get("cues") or []),
        entities=list(data.get("entities") or []),
        platforms=list(data.get("platforms") or []),
    )


def _seed_commlink_statuses(directory) -> dict[str, Any]:
    from uci_common.commlink_messages import CommLinkStatusReport

    statuses: dict[str, Any] = {}
    for link in directory.comm_links:
        statuses[link.id] = CommLinkStatusReport(
            message_id="",
            link_id=link.id,
            resource_id=link.resource_id or "",
            status="active",
            billing_model="flat_rate",
            billing_label="Active",
            reservation_status="none",
            used_minutes=0,
            estimated_cost=0.0,
            currency="USD",
        )
    return statuses


def build_harness_picture(
    *,
    geo_filter: dict[str, Any] | None = None,
    highlight_entity_id: str | None = None,
) -> dict[str, Any]:
    doc = load_harness_document()
    parse_directory_xml = load_omy_module("uci_common/directory_xml.py").parse_directory_xml
    directory = parse_directory_xml(_DIRECTORY_XML.read_text(encoding="utf-8"))
    statuses = _seed_commlink_statuses(directory)
    display = build_commlink_display(directory, statuses, {})
    snap = harness_snapshot(doc)

    picture = build_rf_picture(
        sim_minutes=float(doc.get("sim_minutes", 0)),
        commlink_display=display,
        directory_links=directory.comm_links,
        engine_snapshot=snap,
        scenario=doc.get("scenario") or {},
        emso_conflicts=[],
        highlight_entity_id=highlight_entity_id,
        bus_connected=False,
    )
    assert_rf_picture_contract(picture)
    return apply_geo_filter(picture, geo_filter)


def verify_rf_features(picture: dict[str, Any], expected: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return list of {id, label, passed, detail} for each feature check."""
    expected = expected or load_harness_document().get("expected_features") or {}
    cols = {c["id"]: c for c in (picture.get("spectrum_columns") or {}).get("columns") or []}
    results: list[dict[str, Any]] = []

    def _add(check_id: str, label: str, passed: bool, detail: str = "") -> None:
        results.append({"id": check_id, "label": label, "passed": passed, "detail": detail})

    _add(
        "four_spectrum_columns",
        RF_FEATURE_CHECKS[0][1],
        len(cols) == 4,
        f"columns={list(cols.keys())}",
    )
    _add(
        "threat_radar_assets",
        RF_FEATURE_CHECKS[1][1],
        len(cols.get("threat_radars", {}).get("assets") or []) >= expected.get("min_threat_radars", 1),
    )
    _add(
        "jammer_assets",
        RF_FEATURE_CHECKS[2][1],
        len(cols.get("jammers", {}).get("assets") or []) >= expected.get("min_jammers", 1),
    )
    _add(
        "comm_assets",
        RF_FEATURE_CHECKS[3][1],
        len(cols.get("comm", {}).get("assets") or []) >= expected.get("min_comm_links", 1),
    )
    _add(
        "support_assets",
        RF_FEATURE_CHECKS[4][1],
        len(cols.get("support", {}).get("assets") or []) >= expected.get("min_support_assets", 1),
    )
    support_ids = {a.get("asset_id") for a in cols.get("support", {}).get("assets") or []}
    _add("gps_support", RF_FEATURE_CHECKS[5][1], "GPS_L1" in support_ids)
    _add(
        "jrfl_entries",
        RF_FEATURE_CHECKS[6][1],
        len((picture.get("jrfl") or {}).get("entries") or []) >= expected.get("min_jrfl_entries", 1),
    )
    _add(
        "emcon_areas",
        RF_FEATURE_CHECKS[7][1],
        len(picture.get("emcon_areas") or []) >= expected.get("min_emcon_areas", 1),
    )
    _add(
        "deconfliction_summary",
        RF_FEATURE_CHECKS[8][1],
        bool(picture.get("deconfliction_summary")),
    )
    _add(
        "spectrum_rows",
        RF_FEATURE_CHECKS[9][1],
        len((picture.get("spectrum") or {}).get("rows") or []) > 0,
    )
    _add(
        "overlap_graph",
        RF_FEATURE_CHECKS[10][1],
        "overlap_bands" in (picture.get("spectrum_columns") or {}),
    )
    geo_emitters = sum(1 for e in picture.get("emitters") or [] if e.get("latitude") is not None)
    _add(
        "geo_locations",
        RF_FEATURE_CHECKS[11][1],
        geo_emitters >= 1,
        f"emitters_with_geo={geo_emitters}",
    )
    return results


def all_features_pass(results: list[dict[str, Any]]) -> bool:
    return all(r["passed"] for r in results)
