<script>
  import DataGrid from "./DataGrid.svelte";

  let { picture = {}, selectedEntityId = $bindable(null), onSelectEntity = () => {} } = $props();
  let kindFilter = $state("ALL");

  let allRows = $derived(picture.fusion_rows || []);
  let rows = $derived(
    kindFilter === "ALL" ? allRows : allRows.filter((r) => r.kind === kindFilter)
  );

  const columns = [
    { key: "kind", label: "Kind", width: "90px" },
    { key: "event_type", label: "Event", width: "80px" },
    { key: "source_feed", label: "Feed", width: "80px" },
    { key: "track_id", label: "Track / Signal", width: "140px" },
    { key: "entity_id", label: "Entity", width: "120px" },
    { key: "platform_id", label: "OMS plat", width: "100px", render: (r) => r.entity?.platform_id || "—" },
    {
      key: "score",
      label: "Score",
      width: "60px",
      render: (r) => (r.score != null ? Number(r.score).toFixed(2) : "—"),
    },
    {
      key: "sim_minutes",
      label: "Sim T+",
      width: "70px",
      render: (r) => `T+${Number(r.sim_minutes || 0).toFixed(1)}`,
    },
    { key: "summary", label: "Summary" },
  ];
</script>

<div class="fusion-panel">
  <div class="fusion-header">
    <div class="filters" role="group" aria-label="Fusion filters">
      {#each ["ALL", "CORRELATION", "RAW_TRACK", "SIGNAL"] as k (k)}
        <button type="button" class:active={kindFilter === k} onclick={() => (kindFilter = k)}>{k === "ALL" ? "All" : k}</button>
      {/each}
    </div>
    <h2>Fusion & correlation</h2>
    <p class="hint">
      {picture.threat_picture?.entity_count ?? 0} entities ·
      {picture.threat_picture?.raw_track_buffer ?? 0} raw tracks buffered ·
      {picture.threat_picture?.bulk_air_catalog ?? 0} air /
      {picture.threat_picture?.bulk_ais_catalog ?? 0} AIS /
      {picture.threat_picture?.bulk_mti_catalog ?? 0} MTI catalog
    </p>
  </div>
  <DataGrid
    {rows}
    {columns}
    rowKey="row_id"
    bind:selectedId={selectedEntityId}
    searchPlaceholder="Filter by track, entity, feed…"
    onSelect={(row) => {
      if (row.entity_id) {
        selectedEntityId = row.entity_id;
        onSelectEntity(row.entity_id);
      }
    }}
    emptyMessage="No fusion events — enable Link-16 / AWACS / AIS / MTI feeds"
    detailTitle="Entity / signal report"
  >
    {#snippet children(row)}
      <div class="detail-grid">
        <div>
          <span class="lbl">Row type</span> {row.kind} · {row.event_type}
        </div>
        <div>
          <span class="lbl">Track</span> <code>{row.track_id}</code>
        </div>
        <div>
          <span class="lbl">Entity</span> <code>{row.entity_id || "—"}</code>
        </div>
        {#if row.signal}
          <fieldset>
            <legend>Signal report</legend>
            <pre>{JSON.stringify(row.signal, null, 2)}</pre>
          </fieldset>
        {/if}
        {#if row.track}
          <fieldset>
            <legend>Raw track</legend>
            <pre>{JSON.stringify(row.track, null, 2)}</pre>
          </fieldset>
        {/if}
        {#if row.entity && Object.keys(row.entity).length}
          <fieldset>
            <legend>Correlated entity</legend>
            <pre>{JSON.stringify(row.entity, null, 2)}</pre>
          </fieldset>
        {/if}
      </div>
    {/snippet}
  </DataGrid>
</div>

<style>
  .fusion-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }
  .fusion-header {
    padding: 12px 16px 0;
  }
  .fusion-header h2 {
    margin: 0;
    font-size: 14px;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .hint {
    margin: 4px 0 8px;
    font-size: 11px;
    color: #8899aa;
  }
  .detail-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .lbl {
    color: #8899aa;
    font-size: 10px;
    text-transform: uppercase;
    margin-right: 6px;
  }
  fieldset {
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    margin: 0;
    padding: 8px;
  }
  legend {
    font-size: 10px;
    color: var(--accent);
    padding: 0 4px;
  }
  pre {
    margin: 0;
    font-size: 10px;
    white-space: pre-wrap;
    word-break: break-word;
    color: #c8d8e8;
  }
  code {
    font-size: 11px;
    color: var(--accent);
  }

  .filters { display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
  .filters button { font-size: 10px; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--glass-border); background: transparent; color: var(--text-muted); cursor: pointer; }
  .filters button.active { border-color: var(--accent); color: var(--accent); background: rgba(0,212,255,0.1); }
</style>
