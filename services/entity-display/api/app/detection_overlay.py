"""Build fog-of-war and route-target detection overlays for entity-display."""

from __future__ import annotations

import math
from typing import Any

from app.geo_filter import point_within_route_buffer

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
