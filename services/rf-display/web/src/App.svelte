<script>
  import { onMount, onDestroy } from "svelte";
  import L from "leaflet";
  import { bandLabel, conflictSeverityClass, conflictTypeLabel } from "./lib/rfFormat.js";
  import {
    assetBarStyle,
    formatFreq,
    isJammed,
    isJamming,
    overlapClass,
    COLUMN_META,
  } from "./lib/spectrumColumns.js";

  let map;
  let source = null;
  let showMap = $state(false);
  let selectedAsset = $state(null);

  let picture = $state({
    sim_minutes: 0,
    commlinks: { links: [], contacts: [] },
    emitters: [],
    ew_platforms: [],
    emcon_areas: [],
    spectrum: { rows: [], contested_bands: 0 },
    spectrum_columns: { columns: [], freq_range_mhz: [0, 15000], overlap_bands: [] },
    support_assets: [],
    conflicts: [],
    deconfliction_summary: {},
  });

  const summary = $derived(picture.deconfliction_summary || {});
  const spectrumCols = $derived(picture.spectrum_columns?.columns || []);
  const freqRange = $derived(picture.spectrum_columns?.freq_range_mhz || [0, 15000]);
  const overlapBands = $derived(picture.spectrum_columns?.overlap_bands || []);

  const mapLayers = { emitters: new Map(), jammers: new Map() };

  function applyPayload(data) {
    picture = data;
  }

  function selectAsset(colId, asset) {
    selectedAsset =
      selectedAsset?.asset_id === asset.asset_id && selectedAsset?.column === colId
        ? null
        : { ...asset, column: colId };
  }

  function assetClasses(colId, asset) {
    const classes = ["spectrum-asset"];
    if (asset.highlighted) classes.push("highlighted");
    if (isJammed(asset)) classes.push("jammed");
    if (colId === "jammers" && asset.jamming_active) classes.push("jamming-active");
    if (colId === "jammers" && isJamming(asset)) classes.push("jamming-overlap");
    for (const o of asset.overlaps_with || []) {
      classes.push(overlapClass(o.conflict_type));
    }
    return classes.join(" ");
  }

  function updateMiniMap() {
    if (!map || !showMap) return;

    const seenE = new Set();
    for (const em of picture.emitters || []) {
      if (em.latitude == null || em.longitude == null) continue;
      seenE.add(em.emitter_id);
      const color = em.highlighted ? "#fef08a" : "#f87171";
      const tip = `${em.label} · ${formatFreq(em.frequency_mhz)}`;
      if (mapLayers.emitters.has(em.emitter_id)) {
        const m = mapLayers.emitters.get(em.emitter_id);
        m.setLatLng([em.latitude, em.longitude]);
        m.setTooltipContent(tip);
      } else {
        const m = L.circleMarker([em.latitude, em.longitude], {
          radius: 6,
          fillColor: color,
          color,
          weight: 2,
          fillOpacity: 0.9,
        }).bindTooltip(tip, { className: "rf-tooltip" });
        m.addTo(map);
        mapLayers.emitters.set(em.emitter_id, m);
      }
    }
    for (const [id, layer] of mapLayers.emitters) {
      if (!seenE.has(id)) {
        map.removeLayer(layer);
        mapLayers.emitters.delete(id);
      }
    }

    const seenJ = new Set();
    for (const jam of picture.ew_platforms || []) {
      if (jam.latitude == null || jam.longitude == null) continue;
      seenJ.add(jam.platform_id);
      const color = jam.jamming_active ? "#f59e0b" : "#64748b";
      const tip = `${jam.callsign || jam.platform_id} · ${jam.jamming_active ? "JAMMING" : "standby"}`;
      if (mapLayers.jammers.has(jam.platform_id)) {
        const m = mapLayers.jammers.get(jam.platform_id);
        m.setLatLng([jam.latitude, jam.longitude]);
        m.setStyle({ fillColor: color, color });
        m.setTooltipContent(tip);
      } else {
        const m = L.circleMarker([jam.latitude, jam.longitude], {
          radius: 7,
          fillColor: color,
          color,
          weight: 2,
          fillOpacity: 0.95,
        }).bindTooltip(tip, { className: "rf-tooltip" });
        m.addTo(map);
        mapLayers.jammers.set(jam.platform_id, m);
      }
    }
    for (const [id, layer] of mapLayers.jammers) {
      if (!seenJ.has(id)) {
        map.removeLayer(layer);
        mapLayers.jammers.delete(id);
      }
    }
  }

  $effect(() => {
    updateMiniMap();
  });

  function initMap() {
    if (map) return;
    map = L.map("rf-mini-map", { zoomControl: true, attributionControl: false }).setView([28.2, 48.5], 6);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      maxZoom: 12,
    }).addTo(map);
    setTimeout(() => map?.invalidateSize(), 100);
  }

  function toggleMap() {
    showMap = !showMap;
    if (showMap) {
      setTimeout(initMap, 50);
    }
  }

  onMount(() => {
    source = new EventSource("/api/stream");
    source.onmessage = (ev) => {
      try {
        applyPayload(JSON.parse(ev.data));
      } catch {
        /* ignore */
      }
    };

    fetch("/api/picture")
      .then((r) => r.json())
      .then(applyPayload)
      .catch(() => {});
    applyHighlightFromUrl();
  });

  onDestroy(() => {
    source?.close();
    map?.remove();
  });

  function applyHighlightFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const entityId = params.get("highlight");
    if (!entityId) return;
    fetch("/api/highlight", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entity_id: entityId }),
    }).catch(() => {});
  }

  function freqTicks() {
    const [min, max] = freqRange;
    const ticks = [];
    const steps = 8;
    for (let i = 0; i <= steps; i++) {
      const v = min + ((max - min) * i) / steps;
      ticks.push({ value: v, pct: (i / steps) * 100 });
    }
    return ticks;
  }
</script>

<div class="rf-shell">
  <header class="rf-header">
    <h1>RF Spectrum · EMSO Deconfliction</h1>
    <span class="stat-pill">T+{Math.round(picture.sim_minutes)} min</span>
    <span class="stat-pill">Threat radars <strong>{summary.threat_emitters ?? 0}</strong></span>
    <span class="stat-pill">Jammers <strong>{summary.active_jammers ?? 0}</strong></span>
    <span class="stat-pill">Comm <strong>{picture.commlinks?.summary?.link_count ?? 0}</strong></span>
    <span class="stat-pill">Support <strong>{summary.support_assets ?? 0}</strong></span>
    <span class="stat-pill warn">Overlaps <strong>{summary.spectrum_overlaps ?? 0}</strong></span>
    <span class="stat-pill danger">Jam overlaps <strong>{summary.jam_overlaps ?? 0}</strong></span>
    <span class="stat-pill danger">Conflicts <strong>{summary.total_conflicts ?? 0}</strong></span>
    {#if picture.bus_connected}
      <span class="stat-pill">Redis <strong>live</strong></span>
    {/if}
    <button class="map-toggle" type="button" onclick={toggleMap}>
      {showMap ? "Hide map" : "Show map"}
    </button>
  </header>

  {#if picture.conflicts.length > 0}
    <div class="conflict-strip">
      {#each picture.conflicts as conflict (conflict.conflict_id)}
        <span class="conflict-chip {conflictSeverityClass(conflict.severity)}">
          {conflictTypeLabel(conflict.conflict_type)} · {conflict.summary}
        </span>
      {/each}
    </div>
  {/if}

  <div class="spectrum-workspace">
    <div class="freq-axis">
      <div class="freq-axis-label">Frequency</div>
      {#each freqTicks() as tick (tick.value)}
        <div class="freq-tick" style="bottom: {tick.pct}%">
          <span>{formatFreq(tick.value)}</span>
          <span class="freq-tick-band">{bandLabel(tick.value)}</span>
        </div>
      {/each}
    </div>

    <div class="spectrum-grid">
      {#each spectrumCols as col (col.id)}
        <section class="spectrum-column" data-column={col.id}>
          <header class="column-header" style="--col-accent: {COLUMN_META[col.id]?.color}">
            <span class="column-icon">{COLUMN_META[col.id]?.icon}</span>
            <div>
              <h2>{col.label}</h2>
              {#if col.subtitle}
                <p>{col.subtitle}</p>
              {/if}
            </div>
            <span class="column-count">{col.assets?.length ?? 0}</span>
          </header>

          <div class="column-canvas">
            {#if (col.assets || []).length === 0}
              <div class="column-empty">No assets in band</div>
            {:else}
              {#each col.assets as asset (asset.asset_id)}
                <button
                  type="button"
                  class={assetClasses(col.id, asset)}
                  style={assetBarStyle(asset, freqRange)}
                  onclick={() => selectAsset(col.id, asset)}
                  title="{asset.label} · {formatFreq(asset.frequency_mhz)} · {asset.band || ''}"
                >
                  <span class="asset-label">{asset.label}</span>
                  <span class="asset-freq">{formatFreq(asset.frequency_mhz)}</span>
                  {#if isJammed(asset)}
                    <span class="asset-flag jammed-flag">JAMMED</span>
                  {/if}
                  {#if col.id === "jammers" && asset.jamming_active}
                    <span class="asset-flag jam-flag">TX</span>
                  {/if}
                </button>
              {/each}
            {/if}
          </div>
        </section>
      {/each}
    </div>

    {#if overlapBands.length > 0}
      <aside class="overlap-legend">
        <h3>Band overlaps</h3>
        <ul>
          {#each overlapBands.slice(0, 12) as band, i (`${band.asset_ids?.join("-")}-${i}`)}
            <li class={overlapClass(band.conflict_type)}>
              <span>{formatFreq(band.frequency_mhz)}</span>
              <span>{band.columns?.join(" ↔ ")}</span>
              <span class="badge">{conflictTypeLabel(band.conflict_type)}</span>
            </li>
          {/each}
        </ul>
      </aside>
    {/if}
  </div>

  {#if selectedAsset}
    <footer class="asset-detail">
      <strong>{selectedAsset.label}</strong>
      <span>{formatFreq(selectedAsset.frequency_mhz)} · BW {selectedAsset.bandwidth_mhz} MHz</span>
      <span>{selectedAsset.band}</span>
      {#if selectedAsset.jammed_by?.length}
        <span class="detail-warn">Jammed by: {selectedAsset.jammed_by.map((j) => j.asset_id).join(", ")}</span>
      {/if}
      {#if selectedAsset.jamming_targets?.length}
        <span class="detail-warn">Jamming: {selectedAsset.jamming_targets.map((j) => j.asset_id).join(", ")}</span>
      {/if}
      {#if selectedAsset.overlaps_with?.length}
        <span>Overlaps: {selectedAsset.overlaps_with.map((o) => `${o.column}:${o.asset_id}`).join(" · ")}</span>
      {/if}
    </footer>
  {/if}

  {#if showMap}
    <div class="mini-map-panel">
      <div id="rf-mini-map"></div>
    </div>
  {/if}

  {#if picture.jrfl?.entries?.length}
    <div class="jrfl-strip">
      <span class="jrfl-title">JRFL · {picture.jrfl.ea_authority?.level || "EACA"}</span>
      {#each picture.jrfl.entries as entry (entry.id)}
        <span class="jrfl-chip">{entry.label} {entry.frequency_mhz} MHz · {entry.restriction}</span>
      {/each}
    </div>
  {/if}
</div>
