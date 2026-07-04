/** Geographic area filter geometry (mirrors API geo_filter.py). */

const NM_TO_M = 1852;
const EARTH_RADIUS_M = 6_371_000;

export function haversineNm(lat1, lon1, lat2, lon2) {
  const rlat1 = (lat1 * Math.PI) / 180;
  const rlon1 = (lon1 * Math.PI) / 180;
  const rlat2 = (lat2 * Math.PI) / 180;
  const rlon2 = (lon2 * Math.PI) / 180;
  const dlat = rlat2 - rlat1;
  const dlon = rlon2 - rlon1;
  const a = Math.sin(dlat / 2) ** 2 + Math.cos(rlat1) * Math.cos(rlat2) * Math.sin(dlon / 2) ** 2;
  return (2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(a))) / NM_TO_M;
}

export function pointInPolygon(lat, lon, polygon) {
  let inside = false;
  const n = polygon.length;
  if (n < 3) return false;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const [yi, xi] = polygon[i];
    const [yj, xj] = polygon[j];
    if ((yi > lat) !== (yj > lat) && lon < ((xj - xi) * (lat - yi)) / (yj - yi + 1e-12) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

export function pointInCircle(lat, lon, centerLat, centerLon, radiusNm) {
  return haversineNm(lat, lon, centerLat, centerLon) <= radiusNm;
}

function pointToSegmentDistanceNm(lat, lon, lat1, lon1, lat2, lon2) {
  const mPerDegLat = 111320;
  const mPerDegLon = 111320 * Math.cos((lat * Math.PI) / 180);
  const x = lon * mPerDegLon;
  const y = lat * mPerDegLat;
  const x1 = lon1 * mPerDegLon;
  const y1 = lat1 * mPerDegLat;
  const x2 = lon2 * mPerDegLon;
  const y2 = lat2 * mPerDegLat;
  const dx = x2 - x1;
  const dy = y2 - y1;
  if (dx === 0 && dy === 0) return haversineNm(lat, lon, lat1, lon1);
  const t = Math.max(0, Math.min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy + 1e-12)));
  const projX = x1 + t * dx;
  const projY = y1 + t * dy;
  return Math.hypot(x - projX, y - projY) / NM_TO_M;
}

export function pointNearRoute(lat, lon, points, bufferNm) {
  if (points.length < 2) {
    return points.length === 1 ? haversineNm(lat, lon, points[0][0], points[0][1]) <= bufferNm : false;
  }
  for (let i = 0; i < points.length - 1; i++) {
    const [lat1, lon1] = points[i];
    const [lat2, lon2] = points[i + 1];
    if (pointToSegmentDistanceNm(lat, lon, lat1, lon1, lat2, lon2) <= bufferNm) return true;
  }
  return false;
}

export function geoFilterMatches(lat, lon, geoFilter) {
  if (!geoFilter?.active) return true;
  const geometry = geoFilter.geometry || {};
  if (geoFilter.type === "circle") {
    return pointInCircle(lat, lon, geometry.center_lat, geometry.center_lon, geometry.radius_nm ?? 10);
  }
  if (geoFilter.type === "polygon") {
    return pointInPolygon(lat, lon, geometry.polygon || []);
  }
  if (geoFilter.type === "route") {
    return pointNearRoute(lat, lon, geometry.points || [], geometry.buffer_nm ?? 10);
  }
  return true;
}

export function buildGeoFilterPayload(type, geometry, label = "") {
  return { type, active: true, label, geometry, include_non_geo: false };
}

export const DRAW_MODES = ["circle", "polygon", "route"];

export function filterStyleForType(type) {
  if (type === "circle") return { color: "#38bdf8", fillOpacity: 0.12 };
  if (type === "polygon") return { color: "#a78bfa", fillOpacity: 0.1 };
  if (type === "route") return { color: "#34d399", fillOpacity: 0.08 };
  return { color: "#8fa3c7", fillOpacity: 0.1 };
}
