"""Deterministic entity-display harness from fixture (no live bus)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.detection_overlay import build_detection_overlays
from app.display_logic import build_feed_status_list, derive_affiliation

_REPO_ROOT = Path(__file__).resolve().parents[4]
_HARNESS_SCENARIO = _REPO_ROOT / "fixtures" / "entity-harness-scenario-v1.json"
_DIRECTORY_XML = _REPO_ROOT / "fixtures" / "commlink-directory-v1.1.xml"

ENTITY_FEATURE_CHECKS: list[tuple[str, str]] = [
    ("fog_zones", "fog_zones overlay present"),
    ("route_corridors", "platform route corridors sampled"),
    ("route_target_alerts", "route passes near target alerts"),
    ("detected_tracks", "detected tracks in harness"),
    ("undetected_threats", "undetected threats counted (not leaked as tracks)"),
    ("map_view", "harness map_view for Gulf War bbox"),
    ("overlay_summary", "overlay summary populated"),
]

_FEED_REGISTRY: list[dict[str, str]] = [
    {"feed_id": "platform-fusion", "label": "Platform fusion", "type": "processor", "role": "detection"},
    {"feed_id": "ads-b-sensor", "label": "ADS-B ingest", "type": "sensor", "role": "entity"},
    {"feed_id": "commlink-status", "label": "Commlink status", "type": "status", "role": "comms"},
]


def load_harness_document() -> dict[str, Any]:
    return json.loads(_HARNESS_SCENARIO.read_text(encoding="utf-8"))


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


def _build_commlinks() -> dict[str, Any]:
    from uci_common import build_commlink_display, parse_directory_xml

    directory = parse_directory_xml(_DIRECTORY_XML.read_text(encoding="utf-8"))
    statuses = _seed_commlink_statuses(directory)
    return build_commlink_display(directory, statuses, {})


def _build_tracks(doc: dict[str, Any]) -> list[dict[str, Any]]:
    tracks: list[dict[str, Any]] = []
    for raw in doc.get("detected_tracks") or []:
        threat_level = raw.get("threat_level")
        tags = list(raw.get("tags") or [])
        squawk = raw.get("squawk", "1200")
        tracks.append(
            {
                "track_id": raw["track_id"],
                "callsign": raw.get("callsign", raw["track_id"]),
                "latitude": float(raw["latitude"]),
                "longitude": float(raw["longitude"]),
                "altitude_feet": float(raw.get("altitude_feet", 0)),
                "heading_deg": float(raw.get("heading_deg", 0)),
                "ground_speed_kts": float(raw.get("ground_speed_kts", 0)),
                "squawk": squawk,
                "primary_category": raw.get("primary_category"),
                "sub_category": raw.get("sub_category"),
                "threat_level": threat_level,
                "tags": tags,
                "operator_tags": list(raw.get("operator_tags") or []),
                "promoted": bool(raw.get("promoted", False)),
                "entity_type": raw.get("entity_type", "aircraft"),
                "affiliation": derive_affiliation(threat_level, tags, squawk),
            }
        )
    return tracks


def build_harness_snapshot(doc: dict[str, Any] | None = None) -> dict[str, Any]:
    data = doc or load_harness_document()
    overlays = build_detection_overlays(data)
    feed_ticks = {
        "platform-fusion": {"count": 42, "last_seen": 1_700_000_000.0},
        "ads-b-sensor": {"count": 18, "last_seen": 1_700_000_000.0},
        "commlink-status": {"count": 6, "last_seen": 1_700_000_000.0},
    }
    return {
        "tracks": _build_tracks(data),
        "commlinks": _build_commlinks(),
        "feed_status": build_feed_status_list(_FEED_REGISTRY, feed_ticks, now=1_700_000_010.0),
        "overlays": overlays,
        "map_view": data.get("map_view") or {"center_lat": 29.0, "center_lon": 48.1, "zoom": 7},
        "harness_mode": True,
        "sim_minutes": float(data.get("sim_minutes", 0)),
    }


def verify_entity_features(snapshot: dict[str, Any], expected: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    expected = expected or load_harness_document().get("expected_features") or {}
    overlays = snapshot.get("overlays") or {}
    summary = overlays.get("summary") or {}
    results: list[dict[str, Any]] = []

    def _add(check_id: str, label: str, passed: bool, detail: str = "") -> None:
        results.append({"id": check_id, "label": label, "passed": passed, "detail": detail})

    fog_count = len(overlays.get("fog_zones") or [])
    _add(
        "fog_zones",
        ENTITY_FEATURE_CHECKS[0][1],
        fog_count >= expected.get("min_fog_zones", 1),
        f"fog_zones={fog_count}",
    )

    corridor_count = len(overlays.get("route_corridors") or [])
    _add(
        "route_corridors",
        ENTITY_FEATURE_CHECKS[1][1],
        corridor_count >= expected.get("min_route_corridors", 1),
        f"corridors={corridor_count}",
    )

    alert_count = len(overlays.get("route_target_alerts") or [])
    _add(
        "route_target_alerts",
        ENTITY_FEATURE_CHECKS[2][1],
        alert_count >= expected.get("min_route_target_alerts", 1),
        f"alerts={alert_count}",
    )

    track_count = len(snapshot.get("tracks") or [])
    _add(
        "detected_tracks",
        ENTITY_FEATURE_CHECKS[3][1],
        track_count >= expected.get("min_detected_tracks", 1),
        f"tracks={track_count}",
    )

    undetected = int(summary.get("undetected_threat_count", 0))
    track_ids = {t["track_id"] for t in snapshot.get("tracks") or []}
    undetected_leaked = any(
        tid in track_ids for tid in (t.get("threat_id") for t in load_harness_document().get("undetected_threats") or [])
    )
    _add(
        "undetected_threats",
        ENTITY_FEATURE_CHECKS[4][1],
        undetected >= expected.get("min_undetected_threats", 1) and not undetected_leaked,
        f"undetected={undetected}, leaked={undetected_leaked}",
    )

    map_view = snapshot.get("map_view") or {}
    _add(
        "map_view",
        ENTITY_FEATURE_CHECKS[5][1],
        map_view.get("center_lat") is not None and map_view.get("center_lon") is not None,
        f"center={map_view.get('center_lat')},{map_view.get('center_lon')}",
    )

    _add(
        "overlay_summary",
        ENTITY_FEATURE_CHECKS[6][1],
        bool(summary) and summary.get("fog_zone_count", 0) > 0,
        str(summary),
    )
    return results


def all_features_pass(results: list[dict[str, Any]]) -> bool:
    return all(r["passed"] for r in results)
