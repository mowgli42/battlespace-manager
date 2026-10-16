# Shared dark map base (o-my suite convention)

Every battlespace display map draws on the same key-free dark base map as
`o-my-debrief` and `o-my-mission-plan`, so the plan / battlespace / debrief
consoles look alike in demos. The canonical write-up lives in the reference
repo: [`o-my-debrief/docs/SHARED-DARK-MAP.md`](https://github.com/mowgli42/o-my-debrief/blob/main/docs/SHARED-DARK-MAP.md).

## The convention

| Setting | Value |
| --- | --- |
| Library | Leaflet 1.9.x |
| Tiles | CartoDB "Dark Matter" raster tiles |
| URL template | `https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png` |
| Subdomains | `abcd` |
| `maxZoom` | **12** — regional demo scale, no street-level detail |
| Attribution | `© OSM © CARTO` |
| API key | none; no paid provider |

```js
import { SUITE_DARK_TILES } from "./lib/basemap.js";

const map = L.map(el, { maxZoom: SUITE_DARK_TILES.maxZoom });
L.tileLayer(SUITE_DARK_TILES.url, SUITE_DARK_TILES).addTo(map);
```

Set `maxZoom` on both the map and the tile layer so `fitBounds` / scroll-zoom
cannot outrun the tiles.

## Where it lives in this repo

Each web app is built and shipped on its own (its Dockerfile copies only its
own `web/` directory), so the constant is duplicated per service. Keep the
copies identical.

| Service | Map | Constant |
| --- | --- | --- |
| battlespace-display | `web/src/App.svelte` (`#map`) | `web/src/lib/basemap.js` |
| entity-display | `web/src/App.svelte` (`#map`) | `web/src/lib/basemap.js` |
| rf-display | `web/src/GeoFilterMap.svelte` | `web/src/lib/basemap.js` |

### Static snapshots

`services/battlespace-display/web/src/lib/staticTiles.js` paints a frozen 3×3
tile mosaic for target imagery without Leaflet. `tileUrl()` expands the same
template (subdomain rotation + `@2x`) and `snapshotTiles()` clamps `z` to the
suite `maxZoom`, so a snapshot and the live map use identical tiles.
`staticTiles.test.js` guards this.

## Changing it

Change the reference constant in `o-my-debrief` first, then update the three
copies here and `o-my-mission-plan`.
