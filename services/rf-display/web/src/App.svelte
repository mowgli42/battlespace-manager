<script>
  import { onMount, onDestroy } from "svelte";
  import OverlapConnectors from "./OverlapConnectors.svelte";
  import JrflCorridors from "./JrflCorridors.svelte";
  import FreqBrush from "./FreqBrush.svelte";
  import GeoFilterMap from "./GeoFilterMap.svelte";
  import SpectrumBandOverview from "./SpectrumBandOverview.svelte";
  import InteractionDrilldown from "./InteractionDrilldown.svelte";
  import { bandLabel, conflictSeverityClass, conflictTypeLabel } from "./lib/rfFormat.js";
  import {
    assetBarStyle,
    createFreqScale,
    formatFreq,
    freqTicks,
    isJammed,
    isJamming,
    overlapClass,
    COLUMN_META,
  } from "./lib/spectrumColumns.js";

  let source = null;
  let gridWrapper = $state(null);
  let showGeoMap = $state(false);
  let showColumnDetail = $state(false);
  let harnessMode = $state(false);
  let selectedBandId = $state(null);
  let selectedInteractionId = $state(null);
  let selectedAsset = $state(null);
  let freqScaleMode = $state("symlog");
  let showAllConnectors = $state(false);
  let brushDomain = $state(null);
  let brushResetToken = $state(0);
  let canvasTop = $state(0);

  let picture = $state({
    sim_minutes: 0,
    commlinks: { links: [], contacts: [] },
    emitters: [],
    ew_platforms: [],
    emcon_areas: [],
    spectrum: { rows: [], contested_bands: 0 },
    spectrum_columns: { columns: [], freq_range_mhz: [0, 15000], overlap_bands: [] },
    spectrum_band_summary: { bands: [], interactions: [] },
    support_assets: [],
    conflicts: [],
    deconfliction_summary: {},
    geo_filter: null,
    geo_filter_summary: { active: false },
  });

  const summary = $derived(picture.deconfliction_summary || {});
  const geoSummary = $derived(picture.geo_filter_summary || {});
  const geoFilter = $derived(picture.geo_filter);
  const bandSummary = $derived(picture.spectrum_band_summary || { bands: [], interactions: [] });
  const selectedInteraction = $derived(
    (bandSummary.interactions || []).find((i) => i.interaction_id === selectedInteractionId) || null
  );
  const spectrumCols = $derived(picture.spectrum_columns?.columns || []);
  const freqRange = $derived(picture.spectrum_columns?.freq_range_mhz || [0, 15000]);
  const overlapBands = $derived(picture.spectrum_columns?.overlap_bands || []);
  const jrflEntries = $derived(picture.jrfl?.entries || []);
  const freqScale = $derived(createFreqScale(freqScaleMode, freqRange, brushDomain));
  const axisTicks = $derived(freqTicks(freqScale, freqScaleMode === "linear" ? 8 : 6));
  const brushActive = $derived(brushDomain != null);

  function applyPayload(data) {
    picture = data;
  }

  function refreshPicture() {
    return fetch("/api/picture")
      .then((r) => r.json())
      .then(applyPayload)
      .catch(() => {});
  }

  function selectBand(bandId) {
    if (selectedBandId === bandId) {
      selectedBandId = null;
      selectedInteractionId = null;
      brushDomain = null;
      brushResetToken += 1;
      return;
    }
    selectedBandId = bandId;
    selectedInteractionId = null;
    selectedAsset = null;
    const band = (bandSummary.bands || []).find((b) => b.band_id === bandId);
    if (band?.active_span_mhz) {
      brushDomain = band.active_span_mhz;
      brushResetToken += 1;
    }
  }

  function selectInteraction(interactionId) {
    selectedInteractionId = selectedInteractionId === interactionId ? null : interactionId;
    selectedAsset = null;
    const ix = (bandSummary.interactions || []).find((i) => i.interaction_id === interactionId);
    if (ix?.freq_low_mhz != null && ix?.freq_high_mhz != null) {
      brushDomain = [ix.freq_low_mhz, ix.freq_high_mhz];
      brushResetToken += 1;
    }
  }

  function clearInteraction() {
    selectedInteractionId = null;
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

  $effect(() => {
    if (!gridWrapper) return;
    const measure = () => {
      canvasTop = gridWrapper.querySelector(".column-header")?.offsetHeight ?? 0;
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(gridWrapper);
    return () => ro.disconnect();
  });

  function toggleGeoMap() {
    showGeoMap = !showGeoMap;
  }

  onMount(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((h) => {
        harnessMode = !!h.harness_mode;
      })
      .catch(() => {});

    source = new EventSource("/api/stream");
    source.onmessage = (ev) => {
      try {
        applyPayload(JSON.parse(ev.data));
      } catch {
        /* ignore */
      }
    };

    refreshPicture();
    applyHighlightFromUrl();
  });

  onDestroy(() => {
    source?.close();
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

  function barStyle(asset) {
    return assetBarStyle(asset, freqScale);
  }

  function resetBrush() {
    brushDomain = null;
    brushResetToken += 1;
  }

  function onBrushDomain(domain) {
    brushDomain = domain;
  }

  function onFilterApplied() {
    refreshPicture();
  }

  function onFilterCleared() {
    refreshPicture();
  }
</script>

<div class="rf-shell">
  <header class="rf-header">
    <h1>RF Spectrum · EMSO Deconfliction</h1>
    {#if harnessMode}
      <span class="stat-pill">Harness <strong>sample</strong></span>
    {/if}
    <span class="stat-pill">T+{Math.round(picture.sim_minutes)} min</span>
    <span class="stat-pill">Threat radars <strong>{summary.threat_emitters ?? 0}</strong></span>
    <span class="stat-pill">Jammers <strong>{summary.active_jammers ?? 0}</strong></span>
    <span class="stat-pill">Comm <strong>{picture.commlinks?.summary?.link_count ?? 0}</strong></span>
    <span class="stat-pill">Support <strong>{summary.support_assets ?? 0}</strong></span>
    {#if geoSummary.active}
      <span class="stat-pill warn">Geo filter <strong>{geoSummary.matched_assets ?? 0}</strong></span>
    {/if}
    <span class="stat-pill warn">Overlaps <strong>{summary.spectrum_overlaps ?? 0}</strong></span>
    <span class="stat-pill danger">Jam overlaps <strong>{summary.jam_overlaps ?? 0}</strong></span>
    <span class="stat-pill danger">Conflicts <strong>{summary.total_conflicts ?? 0}</strong></span>
    <span class="stat-pill">ITU bands <strong>{summary.active_itu_bands ?? 0}</strong>/9</span>
    {#if picture.bus_connected}
      <span class="stat-pill">Redis <strong>live</strong></span>
    {/if}
    <div class="scale-toggle" role="group" aria-label="Frequency scale">
      <button type="button" class:active={freqScaleMode === "linear"} onclick={() => (freqScaleMode = "linear")}>Linear</button>
      <button type="button" class:active={freqScaleMode === "log"} onclick={() => (freqScaleMode = "log")}>Log</button>
      <button type="button" class:active={freqScaleMode === "symlog"} onclick={() => (freqScaleMode = "symlog")}>Symlog</button>
    </div>
    {#if brushActive}
      <button type="button" class="brush-reset" onclick={resetBrush}>Reset zoom</button>
    {/if}
    <label class="connector-toggle">
      <input type="checkbox" bind:checked={showAllConnectors} />
      All overlaps
    </label>
    <button class="map-toggle" type="button" onclick={() => (showColumnDetail = !showColumnDetail)}>
      {showColumnDetail ? "Band summary only" : "Column detail"}
    </button>
    <button class="map-toggle" type="button" onclick={toggleGeoMap}>
      {showGeoMap ? "Hide geo map" : "Geo map"}
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

  <SpectrumBandOverview
    bandSummary={bandSummary}
    {selectedBandId}
    {selectedInteractionId}
    onSelectBand={selectBand}
    onSelectInteraction={selectInteraction}
  />

  <InteractionDrilldown interaction={selectedInteraction} onClose={clearInteraction} />

  {#if showColumnDetail}
  <div class="spectrum-workspace">
    <div class="freq-axis-wrap">
      <div class="freq-axis" style="padding-top: {canvasTop}px">
        <div class="freq-axis-label">Frequency</div>
        {#each axisTicks as tick (tick.value)}
          <div class="freq-tick" style="bottom: {tick.pct}%">
            <span>{formatFreq(tick.value)}</span>
            <span class="freq-tick-band">{bandLabel(tick.value)}</span>
          </div>
        {/each}
      </div>
      <FreqBrush
        {gridWrapper}
        {freqScaleMode}
        fullRange={freqRange}
        {brushDomain}
        {brushResetToken}
        onBrushDomain={onBrushDomain}
      />
    </div>

    <div class="spectrum-grid-wrap" bind:this={gridWrapper}>
      <OverlapConnectors
        {gridWrapper}
        overlapBands={overlapBands}
        jamOnly={!showAllConnectors}
        {selectedAsset}
      />

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
              <JrflCorridors entries={jrflEntries} scale={freqScale} />
              {#if (col.assets || []).length === 0}
                <div class="column-empty">
                  {geoSummary.active ? "No assets in area" : "No assets in band"}
                </div>
              {:else}
                {#each col.assets as asset (asset.asset_id)}
                  <button
                    type="button"
                    class={assetClasses(col.id, asset)}
                    style={barStyle(asset)}
                    data-column={col.id}
                    data-asset-id={asset.asset_id}
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
  {/if}

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
    </footer>
  {/if}

  {#if showGeoMap}
    <div class="geo-map-panel">
      <GeoFilterMap
        {picture}
        geoFilter={geoFilter}
        onFilterApplied={onFilterApplied}
        onFilterCleared={onFilterCleared}
      />
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
