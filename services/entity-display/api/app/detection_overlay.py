"""Build fog-of-war and route-target detection overlays for entity-display."""

from __future__ import annotations

import math
from typing import Any

from app.geo_filter import haversine_nm, point_within_route_buffer

NM_TO_DEG_LAT = 1.0 / 60.0


def _route_spec(platform: dict[str, Any]) -> dict[str, Any]:
    if platform.get("route"):
        return dict(platform["route"])
    if "orbit" in platform:
        o = platform["orbit"]
        return {
            "pattern": "orbit",
            "centerLat": o.get("lat"),
            "centerLon": o.get("lon"),
            "radiusNm": o.get("radiusNm", 60),
        }
    ip = platform.get("initialPosition", {})
    return {
        "pattern": "station",
        "centerLat": ip.get("lat", 27.0),
        "centerLon": ip.get("lon", 49.0),
        "radiusNm": 5,
    }


def sample_orbit_points(
    center_lat: float, center_lon: float, radius_nm: float, steps: int = 36
) -> list[list[float]]:
    points: list[list[float]] = []
    cos_lat = max(math.cos(math.radians(center_lat)), 0.2)
    for i in range(steps + 1):
        ang = 2 * math.pi * i / steps
        lat = center_lat + radius_nm * NM_TO_DEG_LAT * math.cos(ang)
        lon = center_lon + radius_nm * NM_TO_DEG_LAT * math.sin(ang) / cos_lat
        points.append([round(lat, 5), round(lon, 5)])
    return points


def sample_racetrack_points(
    center_lat: float, center_lon: float, radius_nm: float, steps: int = 24
) -> list[list[float]]:
    points: list[list[float]] = []
    cos_lat = max(math.cos(math.radians(center_lat)), 0.2)
    for i in range(steps + 1):
        ang = 2 * math.pi * i / steps
        lat = center_lat + radius_nm * 0.6 * NM_TO_DEG_LAT * math.sin(ang)
        lon = center_lon + radius_nm * NM_TO_DEG_LAT * math.cos(ang) / cos_lat
        points.append([round(lat, 5), round(lon, 5)])
    return points


def sample_platform_route(platform: dict[str, Any], steps: int = 36) -> list[list[float]]:
    route = _route_spec(platform)
    pattern = route.get("pattern", "station")
    clat = float(route.get("centerLat", 29.0))
    clon = float(route.get("centerLon", 48.0))
    radius_nm = float(route.get("radiusNm", 40))

    if pattern == "orbit":
        return sample_orbit_points(clat, clon, radius_nm, steps=steps)
    if pattern == "racetrack":
        return sample_racetrack_points(clat, clon, radius_nm, steps=steps)
    if pattern == "transit":
        wps = route.get("waypoints") or []
        return [[float(w["lat"]), float(w["lon"])] for w in wps]
    return [[clat, clon]]


def build_fog_zones(doc: dict[str, Any]) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    for zone in doc.get("fog_zones") or []:
        polygon = zone.get("polygon") or []
        if len(polygon) < 3:
            continue
        zones.append(
            {
                "zone_id": zone.get("zone_id", ""),
                "label": zone.get("label", "Detection gap"),
                "reason": zone.get("reason", "no_sensor_coverage"),
                "opacity": float(zone.get("opacity", 0.5)),
                "polygon": polygon,
            }
        )
    return zones


def build_route_corridors(doc: dict[str, Any]) -> list[dict[str, Any]]:
    detection = doc.get("detection") or {}
    buffer_nm = float(detection.get("route_buffer_nm", 8))
    corridors: list[dict[str, Any]] = []
    scenario = doc.get("scenario") or {}
    for platform in scenario.get("coalitionPlatforms") or []:
        points = sample_platform_route(platform)
        if len(points) < 2:
            continue
        route = _route_spec(platform)
        corridors.append(
            {
                "corridor_id": f"route-{platform.get('platformId', '')}",
                "platform_id": platform.get("platformId", ""),
                "callsign": platform.get("callsign", ""),
                "pattern": route.get("pattern", "unknown"),
                "route_name": route.get("name", route.get("pattern", "")),
                "points": points,
                "buffer_nm": buffer_nm,
            }
        )
    return corridors


def build_route_target_alerts(
    doc: dict[str, Any], corridors: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    corridors = corridors if corridors is not None else build_route_corridors(doc)
    alerts: list[dict[str, Any]] = []
    for target in doc.get("targets") or []:
        lat = target.get("latitude")
        lon = target.get("longitude")
        if lat is None or lon is None:
            continue
        for corridor in corridors:
            buffer_nm = float(corridor.get("buffer_nm", 8))
            points = corridor.get("points") or []
            if not point_within_route_buffer(float(lat), float(lon), points, buffer_nm):
                continue
            alerts.append(
                {
                    "alert_id": f"rta-{target.get('target_id')}-{corridor.get('corridor_id')}",
                    "target_id": target.get("target_id", ""),
                    "target_label": target.get("label", ""),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "platform_id": corridor.get("platform_id", ""),
                    "callsign": corridor.get("callsign", ""),
                    "route_name": corridor.get("route_name", ""),
                    "buffer_nm": buffer_nm,
                    "in_fog": bool(target.get("in_fog", False)),
                    "priority": target.get("priority", "MEDIUM"),
                }
            )
    return alerts


def build_detection_overlays(doc: dict[str, Any]) -> dict[str, Any]:
    fog_zones = build_fog_zones(doc)
    route_corridors = build_route_corridors(doc)
    route_target_alerts = build_route_target_alerts(doc, route_corridors)
    undetected = doc.get("undetected_threats") or []
    return {
        "fog_zones": fog_zones,
        "route_corridors": route_corridors,
        "route_target_alerts": route_target_alerts,
        "summary": {
            "fog_zone_count": len(fog_zones),
            "route_corridor_count": len(route_corridors),
            "route_target_alert_count": len(route_target_alerts),
            "undetected_threat_count": len(undetected),
            "detected_track_count": len(doc.get("detected_tracks") or []),
        },
    }


def _grid_cell_polygon(lat: float, lon: float, cell_deg: float = 0.35) -> list[list[float]]:
    """Coarse sector polygon — does not reveal exact threat coordinates."""
    lat0 = math.floor(lat / cell_deg) * cell_deg
    lon0 = math.floor(lon / cell_deg) * cell_deg
    return [
        [round(lat0, 3), round(lon0, 3)],
        [round(lat0 + cell_deg, 3), round(lon0, 3)],
        [round(lat0 + cell_deg, 3), round(lon0 + cell_deg, 3)],
        [round(lat0, 3), round(lon0 + cell_deg, 3)],
    ]


def _is_covered_by_sensors(
    lat: float,
    lon: float,
    sensors: list[dict[str, Any]],
) -> bool:
    for sensor in sensors:
        if not sensor.get("online", True):
            continue
        radius = float(sensor.get("coverage_radius_nm", 120))
        dist = haversine_nm(
            lat,
            lon,
            float(sensor["latitude"]),
            float(sensor["longitude"]),
        )
        if dist <= radius:
            return True
    return False


def build_dynamic_fog_zones(
    threats: list[dict[str, Any]],
    detected_entity_ids: set[str],
    sensors: list[dict[str, Any]],
    *,
    cell_deg: float = 0.35,
) -> list[dict[str, Any]]:
    """Fog sectors for undetected OPFOR threats (grid cells, no position leak)."""
    zones: list[dict[str, Any]] = []
    cell_counts: dict[tuple[int, int], int] = {}

    for threat in threats:
        tid = threat.get("threat_id", "")
        if not tid or tid in detected_entity_ids:
            continue
        lat = float(threat["latitude"])
        lon = float(threat["longitude"])
        cell = (int(math.floor(lat / cell_deg)), int(math.floor(lon / cell_deg)))
        cell_counts[cell] = cell_counts.get(cell, 0) + 1

    for cell, count in cell_counts.items():
        lat0 = cell[0] * cell_deg + cell_deg / 2
        lon0 = cell[1] * cell_deg + cell_deg / 2
        covered = _is_covered_by_sensors(lat0, lon0, sensors)
        zones.append(
            {
                "zone_id": f"fog-cell-{cell[0]}-{cell[1]}",
                "label": f"Detection gap — sector ({cell[0]},{cell[1]})",
                "reason": "detection_probability_gap" if covered else "no_sensor_coverage",
                "opacity": 0.38 if covered else 0.52,
                "polygon": _grid_cell_polygon(lat0, lon0, cell_deg),
                "undetected_count": count,
            }
        )
    return zones


def build_live_route_corridors(
    scenario: dict[str, Any],
    platforms_live: dict[str, dict[str, Any]],
    *,
    route_buffer_nm: float = 8,
) -> list[dict[str, Any]]:
    from app.scenario_context import merge_live_platforms

    doc = {
        "scenario": {"coalitionPlatforms": merge_live_platforms(scenario, platforms_live)},
        "detection": {"route_buffer_nm": route_buffer_nm},
    }
    return build_route_corridors(doc)


def build_live_detection_overlays(
    scenario: dict[str, Any],
    *,
    platforms_live: dict[str, dict[str, Any]],
    detected_entity_ids: set[str],
    sim_minutes: float = 0.0,
    route_buffer_nm: float = 8.0,
    sensor_coverage_nm: float = 120.0,
    cell_deg: float = 0.35,
) -> dict[str, Any]:
    """Build overlays from scenario ground truth + live bus state (no position leak)."""
    from app.scenario_context import (
        build_sensors,
        ground_truth_threats,
        targets_for_alerts,
    )

    sensors = build_sensors(
        scenario, platforms_live, default_coverage_nm=sensor_coverage_nm
    )
    threats = ground_truth_threats(scenario, sim_minutes)
    undetected_ids = {
        t["threat_id"] for t in threats if t["threat_id"] not in detected_entity_ids
    }

    fog_zones = build_dynamic_fog_zones(
        threats, detected_entity_ids, sensors, cell_deg=cell_deg
    )
    route_corridors = build_live_route_corridors(
        scenario, platforms_live, route_buffer_nm=route_buffer_nm
    )

    alert_doc = {
        "targets": targets_for_alerts(scenario, detected_entity_ids, sim_minutes),
        "detection": {"route_buffer_nm": route_buffer_nm},
    }
    route_target_alerts = build_route_target_alerts(alert_doc, route_corridors)

    return {
        "fog_zones": fog_zones,
        "route_corridors": route_corridors,
        "route_target_alerts": route_target_alerts,
        "summary": {
            "fog_zone_count": len(fog_zones),
            "route_corridor_count": len(route_corridors),
            "route_target_alert_count": len(route_target_alerts),
            "undetected_threat_count": len(undetected_ids),
            "detected_track_count": len(detected_entity_ids),
            "sensor_count": len(sensors),
            "sim_minutes": sim_minutes,
            "live_mode": True,
        },
    }
