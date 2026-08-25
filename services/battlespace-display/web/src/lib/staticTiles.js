/** Slippy-map tile math for a frozen location snapshot (no Leaflet). */

export function hasFix(lat, lon) {
  const a = Number(lat);
  const b = Number(lon);
  return Number.isFinite(a) && Number.isFinite(b) && (Math.abs(a) > 0.02 || Math.abs(b) > 0.02);
}

export function latLonToTile(lat, lon, z) {
  const n = 2 ** z;
  const x = Math.floor(((Number(lon) + 180) / 360) * n);
  const latRad = (Number(lat) * Math.PI) / 180;
  const y = Math.floor(((1 - Math.log(Math.tan(latRad) + 1 / Math.cos(latRad)) / Math.PI) / 2) * n);
  return { x, y, z };
}

export function tileUrl(z, x, y) {
  return `https://basemaps.cartocdn.com/dark_all/${z}/${x}/${y}@2x.png`;
}

export function snapshotTiles(lat, lon, z = 8) {
  if (!hasFix(lat, lon)) return [];
  const c = latLonToTile(lat, lon, z);
  const tiles = [];
  for (let dy = -1; dy <= 1; dy += 1) {
    for (let dx = -1; dx <= 1; dx += 1) {
      tiles.push({
        url: tileUrl(z, c.x + dx, c.y + dy),
        dx,
        dy,
      });
    }
  }
  return tiles;
}

export function seedHue(id) {
  const s = String(id || "task");
  let h = 0;
  for (let i = 0; i < s.length; i += 1) h = (h * 33 + s.charCodeAt(i)) >>> 0;
  return h % 360;
}
