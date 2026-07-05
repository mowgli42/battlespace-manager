/** Geographic helpers (mirrors API geo_filter.py). */

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

export function pointNearRoute(lat, lon, points, bufferNm) {
  if (points.length < 2) {
    return points.length === 1 ? haversineNm(lat, lon, points[0][0], points[0][1]) <= bufferNm : false;
  }
  for (let i = 0; i < points.length - 1; i++) {
    const [lat1, lon1] = points[i];
    const [lat2, lon2] = points[i + 1];
    if (segmentDistanceNm(lat, lon, lat1, lon1, lat2, lon2) <= bufferNm) return true;
  }
  return false;
}

function segmentDistanceNm(lat, lon, lat1, lon1, lat2, lon2) {
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
