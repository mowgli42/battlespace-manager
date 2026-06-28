<script>
  import DataGrid from "./DataGrid.svelte";

  let { picture = {}, selectedEntityId = $bindable(null), onSelectEntity = () => {} } = $props();

  let rows = $derived(picture.platform_context || []);

  const columns = [
    { key: "entity_id", label: "Fused entity", width: "130px" },
    { key: "platform_id", label: "OMS platform", width: "120px" },
    { key: "callsign", label: "Callsign", width: "90px" },
    { key: "platform_type", label: "Type", width: "80px" },
    { key: "readiness", label: "Ready", width: "70px" },
    {
      key: "fuel_percent",
      label: "Fuel %",
      width: "70px",
      render: (r) => (r.fuel_percent != null ? Number(r.fuel_percent).toFixed(0) : "—"),
    },
    {
      key: "weapons_remaining",
      label: "Wpn",
      width: "50px",
      render: (r) => (r.weapons_remaining != null ? String(r.weapons_remaining) : "—"),
    },
    { key: "active_task_id", label: "Task", width: "100px" },
  ];
</script>

<div class="platform-context-panel">
  <div class="header">
    <h2>OMS platform fusion</h2>
    <p class="hint">
      Coalition fused entities linked to OMS platform telemetry · {rows.length} link{rows.length === 1 ? "" : "s"}
    </p>
  </div>
  <DataGrid
    {rows}
    {columns}
    rowKey="entity_id"
    bind:selectedId={selectedEntityId}
    searchPlaceholder="Filter by entity, platform, callsign…"
    onSelect={(row) => {
      if (row.entity_id) {
        selectedEntityId = row.entity_id;
        onSelectEntity(row.entity_id);
      }
    }}
    emptyMessage="No OMS platform links yet — coalition tracks will correlate with platform status"
    detailTitle="OMS platform link detail"
  >
    {#snippet children(row)}
      <div class="detail-grid">
        <div><span class="lbl">Entity</span> <code>{row.entity_id}</code></div>
        <div><span class="lbl">Platform</span> <code>{row.platform_id}</code> · {row.callsign}</div>
        <div><span class="lbl">Readiness</span> {row.readiness}</div>
        {#if row.subsystems && Object.keys(row.subsystems).length}
          <fieldset>
            <legend>Subsystems</legend>
            <pre>{JSON.stringify(row.subsystems, null, 2)}</pre>
          </fieldset>
        {/if}
      </div>
    {/snippet}
  </DataGrid>
</div>

<style>
  .platform-context-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    border-top: 1px solid var(--glass-border);
  }
  .header {
    padding: 12px 16px 0;
    flex-shrink: 0;
  }
  .header h2 {
    margin: 0;
    font-size: 13px;
    color: var(--ok);
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
    color: var(--ok);
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
    color: var(--ok);
  }
</style>
