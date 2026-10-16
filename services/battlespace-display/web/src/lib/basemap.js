/**
 * o-my suite shared dark base map.
 *
 * Same values as the reference implementation in o-my-debrief
 * (frontend/src/lib/basemap.js, docs/SHARED-DARK-MAP.md) and the copy in
 * o-my-mission-plan. Each battlespace web app is built on its own, so the
 * constants are duplicated per service rather than imported across services;
 * keep every copy identical (docs/SHARED-DARK-MAP.md in this repo).
 *
 *   - Tiles        Esri World Dark Gray Canvas: base + reference (labels)
 *   - maxZoom      12  (regional demo scale; no street-level detail)
 *   - opacity      0.65 base / 0.45 labels over a dark (#0b1220-ish) container
 *   - attribution  "© Esri, HERE, Garmin, © OpenStreetMap contributors"
 *   - no API key, no paid provider (CARTO Dark Matter now watermarks un-keyed tiles)
 *
 * Usage (Leaflet):
 *   const map = L.map(el, { maxZoom: SUITE_DARK_TILES.maxZoom });
 *   L.tileLayer(SUITE_DARK_TILES.url, SUITE_DARK_TILES).addTo(map);
 *   L.tileLayer(SUITE_DARK_LABELS.url, SUITE_DARK_LABELS).addTo(map);
 *
 * Intentionally dependency-free so non-Leaflet code (staticTiles.js) can share it.
 */
export const SUITE_DARK_TILES = Object.freeze({
  url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
  attribution: "&copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors",
  maxZoom: 12,
  opacity: 0.65,
});

export const SUITE_DARK_LABELS = Object.freeze({
  url: "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
  maxZoom: SUITE_DARK_TILES.maxZoom,
  opacity: 0.45,
});
