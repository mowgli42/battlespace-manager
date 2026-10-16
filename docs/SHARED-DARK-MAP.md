# Shared dark map base (o-my suite convention)

Every battlespace display map draws on the same key-free dark base map as
`o-my-debrief` and `o-my-mission-plan`, so the plan / battlespace / debrief
consoles look alike in demos. The canonical write-up lives in the reference
repo: [`o-my-debrief/docs/SHARED-DARK-MAP.md`](https://github.com/mowgli42/o-my-debrief/blob/main/docs/SHARED-DARK-MAP.md).

## The convention

| Setting | Value |
| --- | --- |
| Library | Leaflet 1.9.x |
| Tiles | Esri World Dark Gray Canvas — base layer + reference (labels) layer |
| Base URL | `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}` |
| Labels URL | `https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}` |
| `maxZoom` | **12** — regional demo scale, no street-level detail |
| Opacity | base `0.65`, labels `0.45`, over the dark `#08142b` / `#0a1018` map container |
| Attribution | `© Esri, HERE, Garmin, © OpenStreetMap contributors` |
| API key | none; no paid provider |

```js
import { SUITE_DARK_LABELS, SUITE_DARK_TILES } from "./lib/basemap.js";

const map = L.map(el, { maxZoom: SUITE_DARK_TILES.maxZoom });
L.tileLayer(SUITE_DARK_TILES.url, SUITE_DARK_TILES).addTo(map);
L.tileLayer(SUITE_DARK_LABELS.url, SUITE_DARK_LABELS).addTo(map);
```

Set `maxZoom` on both the map and the tile layers so `fitBounds` / scroll-zoom
cannot outrun the tiles. The Esri scheme is `{z}/{y}/{x}` (row before column)
with no `{s}` subdomain and no `{r}` retina suffix.

### Why not CartoDB Dark Matter?

`staticTiles.js` and the live maps used to point at
`basemaps.cartocdn.com/dark_all`. CARTO now serves an "API KEY REQUIRED"
watermark on every un-keyed tile (policy change, September 2026), and the
suite rule is *no key committed, no key required*, so the standard moved to a
provider that is still key-free from any origin.

## Where it lives in this repo

Each web app is built and shipped on its own (its Dockerfile copies only its
own `web/` directory), so the constants are duplicated per service. Keep the
copies identical.

| Service | Map | Constants |
| --- | --- | --- |
| battlespace-display | `web/src/App.svelte` (`#map`) | `web/src/lib/basemap.js` |
| entity-display | `web/src/App.svelte` (`#map`) | `web/src/lib/basemap.js` |
| rf-display | `web/src/GeoFilterMap.svelte` | `web/src/lib/basemap.js` |

### Static snapshots

`services/battlespace-display/web/src/lib/staticTiles.js` paints a frozen 3×3
tile mosaic for target imagery without Leaflet. `tileUrl()` expands the same
base template and `snapshotTiles()` clamps `z` to the suite `maxZoom`, so a
snapshot and the live map use identical tiles. `staticTiles.test.js` guards this.

## Changing it

Change the reference constants in `o-my-debrief` first, then update the three
copies here and `o-my-mission-plan`.
