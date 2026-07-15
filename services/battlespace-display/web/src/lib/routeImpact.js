/** Route-threat map/timeline helpers (battlespace-manager#14). */

export const BAND_NM = { strike: 50, ej: 100, jam: 160 };

export function haversineNm(lat1, lon1, lat2, lon2) {
  const R = 3440.065;
  const toRad = (d) => (d * Math.PI) / 180;
  const φ1 = toRad(lat1);
  const φ2 = toRad(lat2);
  const dφ = toRad(lat2 - lat1);
  const dλ = toRad(lon2 - lon1);
  const a = Math.sin(dφ / 2) ** 2 + Math.cos(φ1) * Math.cos(φ2) * Math.sin(dλ / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(a)));
}

export function bandForDistance(nm) {
  if (nm == null || Number.isNaN(nm) || nm < 0 || nm > BAND_NM.jam) return "OUT";
  if (nm <= BAND_NM.strike) return "STRIKE";
  if (nm <= BAND_NM.ej) return "EJ";
  return "JAM";
}

export function bandColor(band) {
  return (
    {
      STRIKE: "#ef4444",
      EJ: "#f97316",
      JAM: "#a78bfa",
      OUT: "#64748b",
    }[band] || "#64748b"
  );
}

/** Midpoint distance from threat to a route segment. */
export function segmentClosestNm(a, b, threatLat, threatLon) {
  const samples = 8;
  let best = Infinity;
  for (let i = 0; i <= samples; i++) {
    const t = i / samples;
    const lat = a[0] + (b[0] - a[0]) * t;
    const lon = a[1] + (b[1] - a[1]) * t;
    best = Math.min(best, haversineNm(threatLat, threatLon, lat, lon));
  }
  return best;
}

/**
 * Build colored polyline segments from waypoints + threat position.
 * @returns {{ segments: Array, closestIndex: number, cumulativeNm: number[] }}
 */
export function buildImpactSegments(waypoints, threatLat, threatLon, radiusNm = BAND_NM.jam) {
  const pts = (waypoints || []).map((w) =>
    Array.isArray(w) ? [Number(w[0]), Number(w[1])] : [Number(w.lat ?? w.latitude), Number(w.lon ?? w.longitude)]
  );
  const segments = [];
  const cumulativeNm = [0];
  let closestIndex = 0;
  let closestNm = Infinity;

  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i];
    const b = pts[i + 1];
    const len = haversineNm(a[0], a[1], b[0], b[1]);
    cumulativeNm.push(cumulativeNm[cumulativeNm.length - 1] + len);
    const dist = segmentClosestNm(a, b, threatLat, threatLon);
    const inRadius = dist <= radiusNm;
    const band = inRadius ? bandForDistance(dist) : "OUT";
    if (dist < closestNm) {
      closestNm = dist;
      closestIndex = i;
    }
    segments.push({
      index: i,
      latlngs: [a, b],
      length_nm: len,
      closest_nm: dist,
      band,
      color: bandColor(band),
      impacted: inRadius,
    });
  }

  return { segments, closestIndex, closestNm, cumulativeNm, waypoints: pts };
}

/** Map tasks onto distance-along-route (0…totalNm). */
export function placeTasksOnRoute(tasks, routeName, waypoints, cumulativeNm) {
  const total = cumulativeNm[cumulativeNm.length - 1] || 1;
  const pts = waypoints || [];
  return (tasks || [])
    .filter((t) => {
      const rn = t.route_name || "";
      return !routeName || rn === routeName || !rn;
    })
    .map((t) => {
      let along = total * 0.5;
      if (t.latitude && t.longitude && pts.length) {
        let best = Infinity;
        let bestAlong = along;
        for (let i = 0; i < pts.length - 1; i++) {
          const a = pts[i];
          const b = pts[i + 1];
          for (let s = 0; s <= 6; s++) {
            const u = s / 6;
            const lat = a[0] + (b[0] - a[0]) * u;
            const lon = a[1] + (b[1] - a[1]) * u;
            const d = haversineNm(t.latitude, t.longitude, lat, lon);
            if (d < best) {
              best = d;
              bestAlong = cumulativeNm[i] + (cumulativeNm[i + 1] - cumulativeNm[i]) * u;
            }
          }
        }
        along = bestAlong;
      } else if (t.cost_nm != null && pts.length) {
        // Fallback: use cost as offset from closest approach guess
        along = Math.min(total, Math.max(0, Number(t.cost_nm)));
      }
      return {
        ...t,
        along_nm: along,
        pct: (along / total) * 100,
        band: bandForDistance(t.cost_nm),
      };
    });
}
