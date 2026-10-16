/**
 * o-my suite shared dark base map.
 *
 * Same values as the reference implementation in o-my-debrief
 * (frontend/src/lib/basemap.js, docs/SHARED-DARK-MAP.md) and the copy in
 * o-my-mission-plan. Each battlespace web app is built on its own, so the
 * constant is duplicated per service rather than imported across services;
 * keep every copy identical (docs/SHARED-DARK-MAP.md in this repo).
 *
 *   - URL          https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png
 *   - maxZoom      12  (regional demo scale; no street-level detail)
 *   - attribution  "© OSM © CARTO"
 *   - no API key, no paid provider
 *
 * Usage (Leaflet):
 *   const map = L.map(el, { maxZoom: SUITE_DARK_TILES.maxZoom });
 *   L.tileLayer(SUITE_DARK_TILES.url, SUITE_DARK_TILES).addTo(map);
 *
 * Intentionally dependency-free so non-Leaflet code (staticTiles.js) can share it.
 */
export const SUITE_DARK_TILES = Object.freeze({
  url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  attribution: "&copy; OSM &copy; CARTO",
  subdomains: "abcd",
  maxZoom: 12,
});
