<script>
  import { onDestroy } from "svelte";
  import L from "leaflet";

  let {
    picture = {},
    selectedEntityId = $bindable(null),
    phaseFilter = $bindable(null),
  } = $props();

  let fkcmMap = $state(null);
  let mapEl = $state(null);
  let markerLayer = $state(null);
  let trackLayer = $state(null);

  const F2T2EA = ["Find", "Fix", "Track", "Target", "Engage", "Assess"];
  const PHASE_COLORS = {
    Find: "#3b82f6",
    Fix: "#eab308",
    Track: "#22c55e",
    Target: "#f97316",
    Engage: "#ef4444",
    Assess: "#a855f7",
  };

  let targets = $derived(picture.fkcm_targets || []);
  let history = $derived(picture.track_history || {});
  let phaseCounts = $derived.by(() => {
    const c = Object.fromEntries(F2T2EA.map((ph) => [ph, 0]));
    for (const t of targets) {
      if (t.phase in c) c[t.phase] += 1;
    }
    return c;
  });

  let filteredTargets = $derived(
    phaseFilter ? targets.filter((t) => t.phase === phaseFilter) : targets
  );

  let sel = $derived(targets.find((t) => t.target_id === selectedEntityId) || null);

  let assignedPlatform = $derived.by(() => {
    if (!sel?.assigned_platform_id) return null;
    return (picture.platforms || []).find((p) => p.platform_id === sel.assigned_platform_id) || null;
  });

  let assignedTaskRow = $derived.by(() => {
    if (!sel) return null;
    const rows = picture.task_rows || [];
    if (sel.task_id) return rows.find((r) => r.task_id === sel.task_id) || null;
    return rows.find((r) => r.target_entity_id === sel.target_id) || null;
  });

  function flagLabel(f) {
    const labels = {
      recent_update: "Recent",
      awaiting_tasking: "Awaiting tasking",
      bda_miss: "BDA miss",
      stale_track: "Stale",
    };
    return labels[f] || f;
  }

  function selectTarget(row) {
    selectedEntityId = row.target_id;
  }

  function clearSelection() {
    selectedEntityId = null;
  }

  function togglePhase(ph) {
    phaseFilter = phaseFilter === ph ? null : ph;
    if (phaseFilter && sel && sel.phase !== phaseFilter) {
      selectedEntityId = null;
    }
  }

  function destroyMap() {
    if (fkcmMap) {
      fkcmMap.remove();
      fkcmMap = null;
      markerLayer = null;
      trackLayer = null;
    }
  }

  function updateDetailMap() {
    if (!fkcmMap || !sel) return;
    const color = sel.phase_color || PHASE_COLORS[sel.phase] || "#94a3b8";
    const lat = sel.latitude;
    const lon = sel.longitude;
    if (markerLayer) {
      markerLayer.setLatLng([lat, lon]);
      markerLayer.setStyle({ fillColor: color, color: "#ffffff" });
    } else {
      markerLayer = L.circleMarker([lat, lon], {
        radius: 10,
        fillColor: color,
        color: "#ffffff",
        weight: 3,
        fillOpacity: 0.95,
      }).addTo(fkcmMap);
      markerLayer.bindTooltip(`<strong>${sel.target_name}</strong><br/>${sel.phase}`, { direction: "top" });
    }
    if (trackLayer) {
      fkcmMap.removeLayer(trackLayer);
      trackLayer = null;
    }
    const pts = history[sel.target_id];
    if (pts?.length > 1) {
      trackLayer = L.polyline(pts, {
        color,
        weight: 3,
        opacity: 0.75,
        dashArray: sel.phase === "Track" ? null : "6 8",
      }).addTo(fkcmMap);
      fkcmMap.fitBounds(trackLayer.getBounds().pad(0.25), { animate: false, maxZoom: 10 });
    } else {
      fkcmMap.setView([lat, lon], 9, { animate: false });
    }
    setTimeout(() => fkcmMap?.invalidateSize(), 80);
  }

  $effect(() => {
    if (!sel || !mapEl) {
      destroyMap();
      return;
    }
    if (!fkcmMap) {
      fkcmMap = L.map(mapEl, { zoomControl: true }).setView([sel.latitude, sel.longitude], 9);
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: "CARTO",
        maxZoom: 12,
      }).addTo(fkcmMap);
    }
    updateDetailMap();
    return () => destroyMap();
  });

  onDestroy(() => destroyMap());
</script>

<div class="fkcm-layout">
  <header class="fkcm-toolbar">
    <div class="toolbar-top">
      <h2>F2T2EA</h2>
      <span class="hint">
        {targets.length} priority target{targets.length === 1 ? "" : "s"}
        {#if phaseFilter}· filtered: {phaseFilter}{:else}· select a target for map & assignment{/if}
      </span>
    </div>
    <div class="phase-rail" role="tablist" aria-label="F2T2EA phase filter">
      <button
        type="button"
        class="phase-btn"
        class:active={!phaseFilter}
        onclick={() => (phaseFilter = null)}
      >
        <span class="ph-name">All</span>
        <span class="ph-count">{targets.length}</span>
      </button>
      {#each F2T2EA as ph (ph)}
        <button
          type="button"
          class="phase-btn"
          class:active={phaseFilter === ph}
          style="--ph-color: {PHASE_COLORS[ph]}"
          onclick={() => togglePhase(ph)}
          title="{ph}: {phaseCounts[ph]} targets"
        >
          <span class="ph-name">{ph}</span>
          <span class="ph-count">{phaseCounts[ph] ?? 0}</span>
        </button>
      {/each}
    </div>
  </header>

  <div class="fkcm-body" class:has-detail={!!sel}>
    <section class="target-list" aria-label="F2T2EA targets">
      {#if filteredTargets.length === 0}
        <p class="empty">
          {#if phaseFilter}
            No targets in <strong>{phaseFilter}</strong> — try another phase or advance the scenario.
          {:else}
            No HVT kill-chain targets yet — advance scenario (T+15+).
          {/if}
        </p>
      {:else}
        <ul>
          {#each filteredTargets as row (row.target_id)}
            <li>
              <button
                type="button"
                class="target-card"
                class:selected={selectedEntityId === row.target_id}
                onclick={() => selectTarget(row)}
              >
                <div class="card-head">
                  <span class="phase-pill" style="--phase-color: {row.phase_color}">{row.phase}</span>
                  <strong>{row.target_name}</strong>
                  <span class="class">{row.classification}</span>
                </div>
                <div class="card-meta">
                  <span>{row.platform_type || row.domain}</span>
                  <span>{row.last_updated_label}</span>
                  {#if row.assigned_task && row.assigned_task !== "—"}
                    <span class="task-chip">{row.assigned_task}</span>
                  {/if}
                </div>
                {#if row.flags?.length}
                  <div class="flags">
                    {#each row.flags as fl (fl)}
                      <span class="flag flag-{fl}">{flagLabel(fl)}</span>
                    {/each}
                  </div>
                {/if}
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    {#if sel}
      <section class="target-detail" aria-label="Target detail">
        <div class="detail-header">
          <div>
            <h3>{sel.target_name}</h3>
            <p class="sub">{sel.classification} · {sel.platform_type || sel.domain}</p>
          </div>
          <button type="button" class="close-btn" onclick={clearSelection} title="Close detail">✕</button>
        </div>

        <div class="phase-track" aria-label="F2T2EA progress">
          {#each F2T2EA as ph (ph)}
            <span class:on={ph === sel.phase} style={ph === sel.phase ? `--phase-color: ${sel.phase_color}` : ""}>
              {ph}
            </span>
          {/each}
        </div>

        <dl class="detail-grid">
          <div>
            <dt>Location</dt>
            <dd>
              {sel.latitude?.toFixed(4)}°, {sel.longitude?.toFixed(4)}° · {Math.round(sel.altitude_feet || 0)} ft
            </dd>
          </div>
          <div>
            <dt>Updated</dt>
            <dd>{sel.last_updated_label}</dd>
          </div>
          <div>
            <dt>Assigned task</dt>
            <dd>
              {#if sel.assigned_task && sel.assigned_task !== "—"}
                {sel.assigned_task}
                {#if sel.task_status && sel.task_status !== "—"}
                  <span class="status-pill">{sel.task_status}</span>
                {/if}
              {:else}
                —
              {/if}
            </dd>
          </div>
          <div>
            <dt>Assigned asset</dt>
            <dd>
              {#if assignedPlatform}
                <strong>{assignedPlatform.callsign}</strong>
                · {assignedPlatform.platform_type}
                {#if assignedPlatform.operational_role}
                  · {assignedPlatform.operational_role}
                {/if}
                <span class="dim">Fuel {Math.round(assignedPlatform.fuel_percent)}%</span>
              {:else if sel.assigned_platform_id}
                {sel.assigned_platform_id}
              {:else}
                Unassigned
              {/if}
            </dd>
          </div>
          {#if assignedTaskRow?.platform_callsign && !assignedPlatform}
            <div>
              <dt>Platform</dt>
              <dd>{assignedTaskRow.platform_callsign}</dd>
            </div>
          {/if}
          <div>
            <dt>BDA</dt>
            <dd>{sel.bda_status || "—"}</dd>
          </div>
        </dl>

        {#if sel.notes}
          <p class="notes">{sel.notes}</p>
        {/if}

        <div class="map-panel">
          <span class="map-label">Target location & track</span>
          <div class="map-host" bind:this={mapEl}></div>
        </div>
      </section>
    {/if}
  </div>
</div>

<style>
  .fkcm-layout {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }
  .fkcm-toolbar {
    padding: 12px 14px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(6, 12, 24, 0.95);
  }
  .toolbar-top {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin-bottom: 10px;
  }
  .fkcm-toolbar h2 {
    margin: 0;
    font-size: 14px;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .hint {
    font-size: 11px;
    color: #8899aa;
  }
  .phase-rail {
    display: flex;
    gap: 6px;
  }
  .phase-btn {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 6px 4px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 10px;
  }
  .phase-btn:hover {
    border-color: var(--ph-color, var(--accent));
    color: var(--text-primary);
  }
  .phase-btn.active {
    border-color: var(--ph-color, var(--accent));
    background: color-mix(in srgb, var(--ph-color, var(--accent)) 18%, transparent);
    color: var(--ph-color, var(--accent));
    font-weight: 600;
  }
  .ph-name {
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .ph-count {
    font-family: ui-monospace, monospace;
    font-size: 11px;
  }
  .fkcm-body {
    flex: 1;
    display: grid;
    grid-template-columns: 1fr;
    min-height: 0;
  }
  .fkcm-body.has-detail {
    grid-template-columns: minmax(260px, 44%) 1fr;
  }
  .target-list {
    overflow: auto;
    padding: 12px;
    border-right: 1px solid var(--glass-border);
    min-height: 0;
  }
  .target-list ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .target-card {
    width: 100%;
    text-align: left;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid var(--glass-border);
    background: var(--glass-bg);
    color: var(--text-primary);
    cursor: pointer;
  }
  .target-card:hover {
    border-color: var(--accent);
  }
  .target-card.selected {
    outline: 1px solid var(--accent);
    background: rgba(0, 212, 255, 0.08);
  }
  .card-head {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 4px;
  }
  .card-head strong {
    font-size: 13px;
  }
  .class {
    font-size: 10px;
    color: #fca5a5;
    margin-left: auto;
  }
  .phase-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    background: color-mix(in srgb, var(--phase-color) 25%, transparent);
    border: 1px solid var(--phase-color);
    color: var(--phase-color);
    font-weight: 600;
    font-size: 10px;
  }
  .card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    font-size: 10px;
    color: #8899aa;
  }
  .task-chip {
    color: #c8e6ff;
    font-family: ui-monospace, monospace;
  }
  .flags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 6px;
  }
  .flag {
    font-size: 9px;
    padding: 2px 5px;
    border-radius: 3px;
    font-weight: 600;
  }
  .flag-recent_update {
    background: rgba(34, 197, 94, 0.2);
    color: var(--ok);
  }
  .flag-awaiting_tasking {
    background: rgba(249, 115, 22, 0.25);
    color: var(--warn);
  }
  .flag-bda_miss {
    background: rgba(168, 85, 247, 0.3);
    color: #e9d5ff;
  }
  .flag-stale_track {
    background: rgba(148, 163, 184, 0.2);
    color: #94a3b8;
  }
  .empty {
    font-size: 12px;
    color: #8899aa;
    padding: 16px;
  }
  .target-detail {
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: auto;
    padding: 12px 14px;
    gap: 12px;
  }
  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
  }
  .detail-header h3 {
    margin: 0;
    font-size: 16px;
    color: var(--text-primary);
  }
  .sub {
    margin: 4px 0 0;
    font-size: 11px;
    color: #8899aa;
  }
  .close-btn {
    border: 1px solid var(--glass-border);
    background: transparent;
    color: #8899aa;
    border-radius: 6px;
    width: 28px;
    height: 28px;
    cursor: pointer;
  }
  .close-btn:hover {
    color: var(--text-primary);
    border-color: var(--accent);
  }
  .phase-track {
    display: flex;
    gap: 4px;
  }
  .phase-track span {
    flex: 1;
    text-align: center;
    font-size: 9px;
    padding: 6px 2px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.06);
    color: #8899aa;
    text-transform: uppercase;
  }
  .phase-track span.on {
    background: color-mix(in srgb, var(--phase-color, var(--accent)) 35%, transparent);
    color: #fff;
    font-weight: 700;
    border: 1px solid var(--phase-color, var(--accent));
  }
  .detail-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px 16px;
    margin: 0;
  }
  .detail-grid dt {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8899aa;
    margin-bottom: 2px;
  }
  .detail-grid dd {
    margin: 0;
    font-size: 12px;
    line-height: 1.4;
  }
  .status-pill {
    display: inline-block;
    margin-left: 6px;
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 10px;
    background: rgba(34, 197, 94, 0.2);
    color: #86efac;
  }
  .dim {
    display: block;
    font-size: 10px;
    color: #8899aa;
    margin-top: 2px;
  }
  .notes {
    margin: 0;
    font-size: 11px;
    color: #c8e6ff;
    padding: 8px 10px;
    border-radius: 6px;
    background: rgba(0, 212, 255, 0.06);
    border: 1px solid rgba(0, 212, 255, 0.15);
  }
  .map-panel {
    flex: 1;
    min-height: 200px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .map-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--accent);
  }
  .map-host {
    flex: 1;
    min-height: 220px;
    border-radius: 8px;
    border: 1px solid var(--glass-border);
    background: #08142b;
    overflow: hidden;
  }
</style>
