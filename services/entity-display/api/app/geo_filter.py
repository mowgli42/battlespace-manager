"""Geographic helpers for entity-display detection overlays."""

from __future__ import annotations

import math

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


def _point_to_segment_distance_nm(
    lat: float,
    lon: float,
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
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
    return math.hypot(x - proj_x, y - proj_y) / NM_TO_M


def point_near_route(lat: float, lon: float, points: list[list[float]], buffer_nm: float) -> float:
    """Return minimum distance (nm) from point to route polyline."""
    if len(points) < 2:
        if len(points) == 1:
            return haversine_nm(lat, lon, points[0][0], points[0][1])
        return float("inf")
    best = float("inf")
    for i in range(len(points) - 1):
        lat1, lon1 = points[i]
        lat2, lon2 = points[i + 1]
        best = min(best, _point_to_segment_distance_nm(lat, lon, lat1, lon1, lat2, lon2))
    return best


def point_within_route_buffer(
    lat: float, lon: float, points: list[list[float]], buffer_nm: float
) -> bool:
    return point_near_route(lat, lon, points, buffer_nm) <= buffer_nm
