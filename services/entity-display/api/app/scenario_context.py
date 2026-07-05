"""Load Gulf War scenario and build detection context for live overlays."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_SCENARIO = (
    Path(os.environ.get("OMYSIM_ROOT", _REPO_ROOT.parent / "o-my-sim"))
    / "fixtures"
    / "scenarios"
    / "gulf_war_1991.json"
)


def scenario_path() -> Path:
    return Path(os.getenv("ENTITY_SCENARIO_JSON", str(_DEFAULT_SCENARIO)))


def load_scenario(path: Path | None = None) -> dict[str, Any]:
    p = path or scenario_path()
    if not p.is_file():
        raise FileNotFoundError(f"Scenario not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _sensor_feed_id(platform: dict[str, Any]) -> str | None:
    role = (platform.get("role") or "").upper()
    ptype = (platform.get("type") or "").upper()
    caps = {str(c).upper() for c in (platform.get("capabilities") or [])}
    if role == "AWACS" or ptype == "E-3" or "TRACK_FEED" in caps:
        return "AWACS-MAGIC"
    if "ISR" in caps:
        return "MTI-KUWAIT"
    return None


def build_sensors(
    scenario: dict[str, Any],
    platforms_live: dict[str, dict[str, Any]],
    *,
    default_coverage_nm: float = 120.0,
) -> list[dict[str, Any]]:
    sensors: list[dict[str, Any]] = []
    for plat in scenario.get("coalitionPlatforms") or []:
        feed_id = _sensor_feed_id(plat)
        if not feed_id:
            continue
        pid = plat.get("platformId", "")
        live = platforms_live.get(pid) or {}
        if live.get("latitude") is not None:
            lat, lon = float(live["latitude"]), float(live["longitude"])
        elif plat.get("orbit"):
            lat = float(plat["orbit"]["lat"])
            lon = float(plat["orbit"]["lon"])
        elif plat.get("initialPosition"):
            lat = float(plat["initialPosition"]["lat"])
            lon = float(plat["initialPosition"]["lon"])
        else:
            continue
        sensors.append(
            {
                "sensor_id": f"sensor-{pid}",
                "platform_id": pid,
                "callsign": plat.get("callsign", pid),
                "feed_id": feed_id,
                "latitude": lat,
                "longitude": lon,
                "coverage_radius_nm": float(
                    plat.get("coverageRadiusNm") or default_coverage_nm
                ),
                "online": live.get("radar_online", True),
            }
        )
    return sensors


def ground_truth_threats(scenario: dict[str, Any], sim_minutes: float) -> list[dict[str, Any]]:
    threats: list[dict[str, Any]] = []
    for hvt in scenario.get("highValueTargets") or []:
        if (hvt.get("affiliation") or "OPFOR").upper() != "OPFOR":
            continue
        pos = hvt.get("initialPosition") or {}
        if pos.get("lat") is None or pos.get("lon") is None:
            continue
        threats.append(
            {
                "threat_id": hvt.get("entityId", ""),
                "label": hvt.get("name", hvt.get("entityId", "")),
                "latitude": float(pos["lat"]),
                "longitude": float(pos["lon"]),
                "priority": hvt.get("priority", 2),
                "source": "hvt",
            }
        )
    for ev in scenario.get("timeline") or []:
        if ev.get("event") != "POPUP_THREAT":
            continue
        if sim_minutes < float(ev.get("simOffsetMinutes", 0)):
            continue
        pos = ev.get("position") or {}
        if pos.get("lat") is None or pos.get("lon") is None:
            continue
        threats.append(
            {
                "threat_id": ev.get("entityId", ""),
                "label": ev.get("threatType", "POPUP"),
                "latitude": float(pos["lat"]),
                "longitude": float(pos["lon"]),
                "priority": ev.get("priority", 1),
                "source": "popup",
            }
        )
    return threats


def merge_live_platforms(
    scenario: dict[str, Any], platforms_live: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Scenario coalition platforms with live positions for route sampling."""
    merged: list[dict[str, Any]] = []
    for plat in scenario.get("coalitionPlatforms") or []:
        pid = plat.get("platformId", "")
        live = platforms_live.get(pid) or {}
        copy = dict(plat)
        lat = live.get("latitude")
        lon = live.get("longitude")
        if lat is not None and lon is not None:
            if copy.get("orbit"):
                copy["orbit"] = {**copy["orbit"], "lat": lat, "lon": lon}
            elif copy.get("route") and copy["route"].get("pattern") in ("orbit", "racetrack", "cap_station"):
                route = dict(copy["route"])
                route["centerLat"] = lat
                route["centerLon"] = lon
                copy["route"] = route
            else:
                copy["initialPosition"] = {
                    **(copy.get("initialPosition") or {}),
                    "lat": lat,
                    "lon": lon,
                }
        merged.append(copy)
    return merged


def targets_for_alerts(
    scenario: dict[str, Any],
    detected_entity_ids: set[str],
    sim_minutes: float,
) -> list[dict[str, Any]]:
    """Only emit map positions for detected OPFOR targets (no ground-truth leak)."""
    targets: list[dict[str, Any]] = []
    for threat in ground_truth_threats(scenario, sim_minutes):
        tid = threat["threat_id"]
        if tid not in detected_entity_ids:
            continue
        targets.append(
            {
                "target_id": tid,
                "label": threat["label"],
                "latitude": threat["latitude"],
                "longitude": threat["longitude"],
                "priority": "HIGH" if int(threat.get("priority", 2)) <= 2 else "MEDIUM",
                "in_fog": False,
            }
        )
    return targets
