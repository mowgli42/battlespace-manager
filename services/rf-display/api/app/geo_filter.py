"""Geographic area filters for RF picture (circle, polygon zone, route buffer)."""

from __future__ import annotations

import copy
import math
from typing import Any

NM_TO_M = 1852.0
EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    return haversine_m(lat1, lon1, lat2, lon2) / NM_TO_M


def point_in_polygon(lat: float, lon: float, polygon: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon (lat=y, lon=x)."""
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i]
        yj, xj = polygon[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def point_in_circle(lat: float, lon: float, center_lat: float, center_lon: float, radius_nm: float) -> bool:
    return haversine_nm(lat, lon, center_lat, center_lon) <= float(radius_nm)


def _point_to_segment_distance_nm(
    lat: float,
    lon: float,
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """Approximate distance from point to segment using planar projection."""
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))
    x, y = lon * m_per_deg_lon, lat * m_per_deg_lat
    x1, y1 = lon1 * m_per_deg_lon, lat1 * m_per_deg_lat
    x2, y2 = lon2 * m_per_deg_lon, lat2 * m_per_deg_lat
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return haversine_nm(lat, lon, lat1, lon1)
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy + 1e-12)))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    dist_m = math.hypot(x - proj_x, y - proj_y)
    return dist_m / NM_TO_M


def point_near_route(lat: float, lon: float, points: list[list[float]], buffer_nm: float) -> bool:
    if len(points) < 2:
        if len(points) == 1:
            return haversine_nm(lat, lon, points[0][0], points[0][1]) <= buffer_nm
        return False
    for i in range(len(points) - 1):
        lat1, lon1 = points[i]
        lat2, lon2 = points[i + 1]
        if _point_to_segment_distance_nm(lat, lon, lat1, lon1, lat2, lon2) <= buffer_nm:
            return True
    return False


def geo_filter_matches(lat: float, lon: float, geo_filter: dict[str, Any]) -> bool:
    if not geo_filter or not geo_filter.get("active"):
        return True

    geometry = geo_filter.get("geometry") or {}
    ftype = geo_filter.get("type", "")

    if ftype == "circle":
        return point_in_circle(
            lat,
            lon,
            float(geometry["center_lat"]),
            float(geometry["center_lon"]),
            float(geometry.get("radius_nm", 10)),
        )
    if ftype == "polygon":
        return point_in_polygon(lat, lon, geometry.get("polygon") or [])
    if ftype == "route":
        return point_near_route(
            lat,
            lon,
            geometry.get("points") or [],
            float(geometry.get("buffer_nm", 10)),
        )
    return True


def asset_has_location(asset: dict[str, Any]) -> bool:
    return asset.get("latitude") is not None and asset.get("longitude") is not None


def asset_in_geo_filter(asset: dict[str, Any], geo_filter: dict[str, Any] | None) -> bool:
    if not geo_filter or not geo_filter.get("active"):
        return True
    if not asset_has_location(asset):
        return bool(geo_filter.get("include_non_geo", False))
    return geo_filter_matches(float(asset["latitude"]), float(asset["longitude"]), geo_filter)


def _filter_list(items: list[dict[str, Any]], geo_filter: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not geo_filter or not geo_filter.get("active"):
        return items
    return [item for item in items if asset_in_geo_filter(item, geo_filter)]


def _filter_column_assets(columns: dict[str, list[dict[str, Any]]], geo_filter: dict[str, Any] | None) -> None:
    for assets in columns.values():
        kept_ids = {a["asset_id"] for a in assets if asset_in_geo_filter(a, geo_filter)}
        assets[:] = [a for a in assets if a["asset_id"] in kept_ids]
        for asset in assets:
            asset["overlaps_with"] = [
                o for o in asset.get("overlaps_with", []) if o.get("asset_id") in kept_ids
            ]
            asset["jammed_by"] = [j for j in asset.get("jammed_by", []) if j.get("asset_id") in kept_ids]
            asset["jamming_targets"] = [
                t for t in asset.get("jamming_targets", []) if t.get("asset_id") in kept_ids
            ]


def apply_geo_filter(picture: dict[str, Any], geo_filter: dict[str, Any] | None) -> dict[str, Any]:
    """Return a copy of picture with geo-filtered asset lists and summary."""
    out = copy.deepcopy(picture)
    out["geo_filter"] = geo_filter

    if not geo_filter or not geo_filter.get("active"):
        out["geo_filter_summary"] = {"active": False, "matched_assets": 0, "hidden_assets": 0}
        return out

    emitters = _filter_list(out.get("emitters") or [], geo_filter)
    ew_platforms = _filter_list(out.get("ew_platforms") or [], geo_filter)
    support_assets = _filter_list(out.get("support_assets") or [], geo_filter)

    total_before = (
        len(out.get("emitters") or [])
        + len(out.get("ew_platforms") or [])
        + len(out.get("support_assets") or [])
        + sum(len(c.get("assets") or []) for c in (out.get("spectrum_columns") or {}).get("columns") or [])
    )

    out["emitters"] = emitters
    out["ew_platforms"] = ew_platforms
    out["support_assets"] = support_assets

    spectrum_columns = out.get("spectrum_columns") or {}
    columns_by_id = {
        c["id"]: c.get("assets") or [] for c in spectrum_columns.get("columns") or []
    }
    _filter_column_assets(columns_by_id, geo_filter)
    for col in spectrum_columns.get("columns") or []:
        col["assets"] = columns_by_id.get(col["id"], [])

    overlap_bands = []
    for band in spectrum_columns.get("overlap_bands") or []:
        ids = set(band.get("asset_ids") or [])
        visible = set()
        for col in spectrum_columns.get("columns") or []:
            for asset in col.get("assets") or []:
                if asset["asset_id"] in ids:
                    visible.add(asset["asset_id"])
        if len(visible) >= 2:
            overlap_bands.append(band)
    spectrum_columns["overlap_bands"] = overlap_bands
    spectrum_columns["overlap_count"] = len(overlap_bands)

    matched = (
        len(emitters)
        + len(ew_platforms)
        + len(support_assets)
        + sum(len(c.get("assets") or []) for c in spectrum_columns.get("columns") or [])
    )

    out["geo_filter_summary"] = {
        "active": True,
        "type": geo_filter.get("type"),
        "label": geo_filter.get("label"),
        "matched_assets": matched,
        "hidden_assets": max(0, total_before - matched),
    }

    summary = dict(out.get("deconfliction_summary") or {})
    summary["geo_filter_active"] = True
    summary["geo_matched_assets"] = matched
    out["deconfliction_summary"] = summary
    return out


def validate_geo_filter(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["geo_filter must be a dict"]
    ftype = payload.get("type")
    if ftype not in ("circle", "polygon", "route"):
        errors.append("type must be circle, polygon, or route")
    geometry = payload.get("geometry") or {}
    if ftype == "circle":
        for key in ("center_lat", "center_lon", "radius_nm"):
            if key not in geometry:
                errors.append(f"circle geometry missing {key}")
    elif ftype == "polygon":
        poly = geometry.get("polygon") or []
        if len(poly) < 3:
            errors.append("polygon needs at least 3 points")
    elif ftype == "route":
        pts = geometry.get("points") or []
        if len(pts) < 2:
            errors.append("route needs at least 2 points")
    return errors
