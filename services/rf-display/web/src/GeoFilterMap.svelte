<script>
  import { onMount, onDestroy } from "svelte";
  import L from "leaflet";
  import {
    buildGeoFilterPayload,
    filterStyleForType,
    haversineNm,
  } from "./lib/geoFilter.js";
  import { formatFreq } from "./lib/spectrumColumns.js";

  let {
    picture = {},
    geoFilter = null,
    onFilterApplied = () => {},
    onFilterCleared = () => {},
  } = $props();

  let map;
  let mapEl = $state(null);
  let drawMode = $state(null);
  let routeBufferNm = $state(10);
  let draftPoints = $state([]);
  let draftLayer = null;
  let filterLayer = null;
  let assetLayers = { emitters: new Map(), jammers: new Map(), support: new Map() };
  let emconLayers = new Map();

  const emitters = $derived(picture.emitters || []);
  const jammers = $derived(picture.ew_platforms || []);
  const support = $derived(picture.support_assets || []);
  const emconAreas = $derived(picture.emcon_areas || []);

  function clearDraft() {
    draftPoints = [];
    if (draftLayer && map) {
      map.removeLayer(draftLayer);
      draftLayer = null;
    }
  }

  function setDrawMode(mode) {
    drawMode = drawMode === mode ? null : mode;
    clearDraft();
  }

  function renderFilterOverlay(filter) {
    if (!map) return;
    if (filterLayer) {
      map.removeLayer(filterLayer);
      filterLayer = null;
    }
    if (!filter?.active) return;

    const style = filterStyleForType(filter.type);
    const g = filter.geometry || {};
    filterLayer = L.layerGroup();

    if (filter.type === "circle") {
      L.circle([g.center_lat, g.center_lon], {
        radius: (g.radius_nm || 10) * 1852,
        color: style.color,
        fillColor: style.color,
        fillOpacity: style.fillOpacity,
        weight: 2,
        dashArray: "6 4",
      })
        .bindTooltip(filter.label || "Area filter")
        .addTo(filterLayer);
    } else if (filter.type === "polygon") {
      L.polygon(g.polygon || [], {
        color: style.color,
        fillColor: style.color,
        fillOpacity: style.fillOpacity,
        weight: 2,
      })
        .bindTooltip(filter.label || "Zone filter")
        .addTo(filterLayer);
    } else if (filter.type === "route") {
      const pts = g.points || [];
      L.polyline(pts, { color: style.color, weight: 3 }).addTo(filterLayer);
      L.polyline(pts, {
        color: style.color,
        weight: (g.buffer_nm || 10) * 0.15,
        opacity: style.fillOpacity,
      }).addTo(filterLayer);
      for (const [lat, lon] of pts) {
        L.circleMarker([lat, lon], { radius: 4, color: style.color, fillOpacity: 0.9 }).addTo(filterLayer);
      }
    }
    filterLayer.addTo(map);
  }

  function applyFilter(payload) {
    fetch("/api/geo-filter", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.status === "ok") onFilterApplied(data);
      })
      .catch(() => {});
    clearDraft();
    drawMode = null;
  }

  function clearFilter() {
    fetch("/api/geo-filter", { method: "DELETE" })
      .then((r) => r.json())
      .then((data) => onFilterCleared(data))
      .catch(() => {});
    clearDraft();
    drawMode = null;
  }

  function finishPolygon() {
    if (draftPoints.length < 3) return;
    applyFilter(
      buildGeoFilterPayload("polygon", { polygon: draftPoints.map((p) => [p.lat, p.lng]) }, "Zone"),
    );
  }

  function finishRoute() {
    if (draftPoints.length < 2) return;
    applyFilter(
      buildGeoFilterPayload(
        "route",
        {
          points: draftPoints.map((p) => [p.lat, p.lng]),
          buffer_nm: routeBufferNm,
        },
        "Route corridor",
      ),
    );
  }

  function onMapClick(e) {
    if (!drawMode) return;
    const { lat, lng } = e.latlng;

    if (drawMode === "circle") {
      if (draftPoints.length === 0) {
        draftPoints = [{ lat, lng }];
      } else {
        const center = draftPoints[0];
        const radiusNm = haversineNm(center.lat, center.lng, lat, lng);
        applyFilter(
          buildGeoFilterPayload(
            "circle",
            { center_lat: center.lat, center_lon: center.lng, radius_nm: Math.max(1, radiusNm) },
            "Circle",
          ),
        );
      }
      return;
    }

    draftPoints = [...draftPoints, { lat, lng }];
    if (draftLayer) map.removeLayer(draftLayer);
    const latlngs = draftPoints.map((p) => [p.lat, p.lng]);
    if (drawMode === "polygon" && draftPoints.length >= 2) {
      draftLayer = L.polygon(latlngs, { color: "#a78bfa", dashArray: "4 6", fillOpacity: 0.05 }).addTo(map);
    } else if (drawMode === "route" && draftPoints.length >= 1) {
      draftLayer = L.polyline(latlngs, { color: "#34d399", dashArray: "6 4" }).addTo(map);
    }
  }

  function updateAssets() {
    if (!map) return;

    const syncMarkers = (items, layerMap, colorFn, idKey) => {
      const seen = new Set();
      for (const item of items) {
        const lat = item.latitude;
        const lon = item.longitude;
        if (lat == null || lon == null) continue;
        const id = item[idKey];
        seen.add(id);
        const color = colorFn(item);
        const tip = item.label || item.callsign || id;
        if (layerMap.has(id)) {
          const m = layerMap.get(id);
          m.setLatLng([lat, lon]);
          m.setStyle({ fillColor: color, color });
          m.setTooltipContent(`${tip} · ${formatFreq(item.frequency_mhz)}`);
        } else {
          const m = L.circleMarker([lat, lon], {
            radius: 7,
            fillColor: color,
            color,
            weight: 2,
            fillOpacity: 0.9,
          }).bindTooltip(`${tip} · ${formatFreq(item.frequency_mhz)}`, { className: "rf-tooltip" });
          m.addTo(map);
          layerMap.set(id, m);
        }
      }
      for (const [id, layer] of layerMap) {
        if (!seen.has(id)) {
          map.removeLayer(layer);
          layerMap.delete(id);
        }
      }
    };

    syncMarkers(emitters, assetLayers.emitters, (e) => (e.highlighted ? "#fef08a" : "#f87171"), "emitter_id");
    syncMarkers(
      jammers,
      assetLayers.jammers,
      (j) => (j.jamming_active ? "#f59e0b" : "#64748b"),
      "platform_id",
    );
    syncMarkers(support, assetLayers.support, () => "#34d399", "asset_id");

    const seenEmcon = new Set();
    for (const area of emconAreas) {
      seenEmcon.add(area.id);
      const latlngs = (area.polygon || []).map((p) => [p[0], p[1]]);
      if (emconLayers.has(area.id)) {
        emconLayers.get(area.id).setLatLngs(latlngs);
      } else {
        const poly = L.polygon(latlngs, {
          color: "#a78bfa",
          fillColor: "#a78bfa",
          weight: 1,
          fillOpacity: 0.06,
          dashArray: "4 6",
        }).bindTooltip(area.name || area.id);
        poly.addTo(map);
        emconLayers.set(area.id, poly);
      }
    }
    for (const [id, layer] of emconLayers) {
      if (!seenEmcon.has(id)) {
        map.removeLayer(layer);
        emconLayers.delete(id);
      }
    }
  }

  $effect(() => {
    emitters;
    jammers;
    support;
    emconAreas;
    updateAssets();
  });

  $effect(() => {
    geoFilter;
    renderFilterOverlay(geoFilter);
  });

  onMount(() => {
    if (!mapEl) return;
    map = L.map(mapEl, { zoomControl: true }).setView([28.8, 48.2], 7);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 12,
    }).addTo(map);
    map.on("click", onMapClick);
    setTimeout(() => map?.invalidateSize(), 100);
    updateAssets();
    renderFilterOverlay(geoFilter);
  });

  onDestroy(() => {
    map?.remove();
  });
</script>

<div class="geo-filter-map">
  <div class="geo-toolbar">
    <span class="geo-toolbar-label">Area filter</span>
    <button type="button" class:active={drawMode === "circle"} onclick={() => setDrawMode("circle")}>
      Circle
    </button>
    <button type="button" class:active={drawMode === "polygon"} onclick={() => setDrawMode("polygon")}>
      Zone
    </button>
    <button type="button" class:active={drawMode === "route"} onclick={() => setDrawMode("route")}>
      Route
    </button>
    {#if drawMode === "polygon" && draftPoints.length >= 3}
      <button type="button" class="geo-action" onclick={finishPolygon}>Close zone</button>
    {/if}
    {#if drawMode === "route" && draftPoints.length >= 2}
      <label class="route-buffer">
        Buffer nm
        <input type="number" min="1" max="200" bind:value={routeBufferNm} />
      </label>
      <button type="button" class="geo-action" onclick={finishRoute}>Finish route</button>
    {/if}
    {#if geoFilter?.active}
      <button type="button" class="geo-clear" onclick={clearFilter}>Clear filter</button>
    {/if}
    {#if drawMode === "circle"}
      <span class="geo-hint">Click center, then edge for radius</span>
    {:else if drawMode === "polygon"}
      <span class="geo-hint">Click vertices · Close zone when ready</span>
    {:else if drawMode === "route"}
      <span class="geo-hint">Click waypoints along route</span>
    {/if}
  </div>
  <div class="geo-map-canvas" bind:this={mapEl}></div>
</div>
