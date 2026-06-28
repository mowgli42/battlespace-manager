<script>
  import DataGrid from "./DataGrid.svelte";

  let { picture = {}, selectedEntityId = $bindable(null), onSelectEntity = () => {} } = $props();

  let rows = $derived(picture.bda_items || []);

  const columns = [
    { key: "target_name", label: "Target", width: "140px" },
    { key: "phase", label: "Phase", width: "70px" },
    { key: "bda_status", label: "BDA", width: "100px" },
    { key: "assigned_task", label: "Task", width: "100px" },
    { key: "task_status", label: "Status", width: "90px" },
    { key: "notes", label: "Notes" },
  ];

  function pick(row) {
    selectedEntityId = row.target_id;
    onSelectEntity(row.target_id);
  }
</script>

<div class="assess-panel">
  <header>
    <h2>BDA / Assess</h2>
    <p class="hint">Post-engagement status · restrike logic (sim)</p>
  </header>
  <DataGrid
    {rows}
    {columns}
    rowKey="target_id"
    bind:selectedId={selectedEntityId}
    onSelect={pick}
    searchPlaceholder="Search BDA outcomes…"
    emptyMessage="No targets in Assess phase yet — advance scenario past engagement"
    detailTitle="BDA detail"
  >
    {#snippet children(row)}
      <p><strong>{row.target_name}</strong> (<code>{row.target_id}</code>)</p>
      <p>BDA: <strong>{row.bda_status}</strong> · Task {row.assigned_task} ({row.task_status})</p>
      <p>{row.notes || "—"}</p>
      {#if row.bda_status === "Miss"}
        <p class="restrike">Restrike recommended (sim)</p>
      {/if}
    {/snippet}
  </DataGrid>
</div>

<style>
  .assess-panel {
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
    color: #a855f7;
    text-transform: uppercase;
  }
  .hint {
    margin: 4px 0 8px;
    font-size: 11px;
    color: var(--text-muted);
  }
  .restrike {
    color: var(--warn);
    font-weight: 600;
    font-size: 12px;
  }
</style>
