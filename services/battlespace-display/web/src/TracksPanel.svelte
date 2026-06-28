<script>
  import DataGrid from "./DataGrid.svelte";

  let { picture = {}, selectedEntityId = $bindable(null), onSelectEntity = () => {} } = $props();

  let rows = $derived(picture.entity_registry || []);

  const columns = [
    { key: "entity_id", label: "Entity", width: "110px" },
    { key: "platform_type", label: "Type", width: "90px" },
    { key: "domain", label: "Domain", width: "70px" },
    {
      key: "affiliation",
      label: "Affil",
      width: "70px",
      html: (r) =>
        `<span class="aff-${(r.affiliation || "").toLowerCase()}">${r.affiliation}</span>`,
    },
    { key: "kill_chain_phase", label: "F2T2EA", width: "70px" },
    {
      key: "confidence",
      label: "Conf",
      width: "50px",
      render: (r) => (r.confidence != null ? `${Math.round(r.confidence * 100)}%` : "—"),
    },
    { key: "staleness", label: "Fresh", width: "60px" },
    {
      key: "sources",
      label: "Sources",
      render: (r) => (r.sources?.length ? r.sources.slice(0, 2).join(", ") : "—"),
    },
  ];

  function pick(row) {
    selectedEntityId = row.entity_id;
    onSelectEntity(row.entity_id);
  }
</script>

<div class="tracks-panel">
  <header>
    <h2>Track registry</h2>
    <p class="hint">Identity · kinematics · confidence · contributing feeds · F2T2EA phase</p>
  </header>
  <DataGrid
    {rows}
    {columns}
    rowKey="entity_id"
    bind:selectedId={selectedEntityId}
    onSelect={pick}
    searchPlaceholder="Search entity, type, track ID…"
    emptyMessage="No correlated entities yet"
    detailTitle="Track detail"
  >
    {#snippet children(row)}
      <dl class="detail-dl">
        <dt>Track IDs</dt>
        <dd><code>{row.sources?.join(", ") || row.track_label}</code></dd>
        <dt>Position</dt>
        <dd>{row.latitude?.toFixed(3)}°, {row.longitude?.toFixed(3)}° · {Math.round(row.altitude_feet || 0)} ft</dd>
        <dt>Last update</dt>
        <dd>T+{row.last_updated_sim} · {row.staleness}</dd>
        {#if row.flags?.length}
          <dt>Flags</dt>
          <dd>{row.flags.join(", ")}</dd>
        {/if}
      </dl>
    {/snippet}
  </DataGrid>
</div>

<style>
  .tracks-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }
  header {
    padding: 12px 16px 0;
  }
  h2 {
    margin: 0;
    font-size: 14px;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .hint {
    margin: 4px 0 8px;
    font-size: 11px;
    color: var(--text-muted);
  }
  .detail-dl {
    display: grid;
    grid-template-columns: 90px 1fr;
    gap: 4px 8px;
    margin: 0;
    font-size: 11px;
  }
  dt {
    color: var(--text-muted);
    text-transform: uppercase;
    font-size: 9px;
  }
  :global(.aff-opfor) {
    color: var(--danger);
    font-weight: 600;
  }
  :global(.aff-coalition) {
    color: var(--ok);
  }
</style>
