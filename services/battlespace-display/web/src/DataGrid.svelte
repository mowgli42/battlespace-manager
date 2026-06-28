<script>
  /**
   * Reusable sortable, searchable datagrid with row selection and detail panel.
   * @type {{
   *   rows: any[],
   *   columns: { key: string, label: string, sortable?: boolean, width?: string, render?: (row: any) => string }[],
   *   rowKey?: string,
   *   searchPlaceholder?: string,
   *   emptyMessage?: string,
   *   selectedId?: string | null,
   *   onSelect?: (row: any) => void,
   *   detailTitle?: string
   * }}
   */
  let {
    rows = [],
    columns = [],
    rowKey = "row_id",
    searchPlaceholder = "Search…",
    emptyMessage = "No rows",
    selectedId = $bindable(null),
    onSelect = () => {},
    detailTitle = "Details",
    children,
  } = $props();

  let query = $state("");
  let sortKey = $state("");
  let sortDir = $state(1);

  function cellValue(row, col) {
    if (col.render) return col.render(row);
    const v = row[col.key];
    if (v == null || v === "") return "—";
    if (Array.isArray(v)) return v.join(", ");
    return String(v);
  }

  function toggleSort(key) {
    if (sortKey === key) sortDir *= -1;
    else {
      sortKey = key;
      sortDir = 1;
    }
  }

  let filtered = $derived.by(() => {
    const q = query.trim().toLowerCase();
    let list = rows;
    if (q) {
      list = rows.filter((r) =>
        columns.some((c) => cellValue(r, c).toLowerCase().includes(q))
      );
    }
    if (sortKey) {
      const col = columns.find((c) => c.key === sortKey);
      list = [...list].sort((a, b) => {
        const av = col?.render ? col.render(a) : a[sortKey];
        const bv = col?.render ? col.render(b) : b[sortKey];
        const an = typeof av === "number" ? av : String(av ?? "").toLowerCase();
        const bn = typeof bv === "number" ? bv : String(bv ?? "").toLowerCase();
        if (an < bn) return -1 * sortDir;
        if (an > bn) return 1 * sortDir;
        return 0;
      });
    }
    return list;
  });

  let selectedRow = $derived(rows.find((r) => r[rowKey] === selectedId || r.task_id === selectedId || r.target_id === selectedId));

  function pick(row) {
    const id = row[rowKey] ?? row.task_id ?? row.target_id;
    selectedId = id;
    onSelect(row);
  }
</script>

<div class="dg-wrap">
  <div class="dg-toolbar">
    <input type="search" class="dg-search" placeholder={searchPlaceholder} bind:value={query} />
    <span class="dg-count">{filtered.length} / {rows.length}</span>
  </div>
  <div class="dg-scroll">
    <table class="dg-table">
      <thead>
        <tr>
          {#each columns as col}
            <th style={col.width ? `min-width:${col.width}` : ""}>
              {#if col.sortable !== false}
                <button type="button" class="dg-sort" onclick={() => toggleSort(col.key)}>
                  {col.label}
                  {#if sortKey === col.key}{sortDir > 0 ? " ▲" : " ▼"}{/if}
                </button>
              {:else}
                {col.label}
              {/if}
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each filtered as row (row[rowKey] ?? row.task_id ?? row.target_id)}
          {@const rid = row[rowKey] ?? row.task_id ?? row.target_id}
          <tr
            class:selected={selectedId === rid}
            onclick={() => pick(row)}
          >
            {#each columns as col}
              <td>{@html col.html ? col.html(row) : cellValue(row, col)}</td>
            {/each}
          </tr>
        {:else}
          <tr><td colspan={columns.length || 1} class="dg-empty">{emptyMessage}</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
  {#if selectedRow && children}
    <div class="dg-detail">
      <strong>{detailTitle}</strong>
      {@render children(selectedRow)}
    </div>
  {/if}
</div>

<style>
  .dg-wrap {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    background: rgba(6, 12, 24, 0.95);
  }
  .dg-toolbar {
    display: flex;
    gap: 12px;
    align-items: center;
    padding: 10px 14px;
    border-bottom: 1px solid var(--glass-border);
  }
  .dg-search {
    flex: 1;
    max-width: 320px;
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid var(--glass-border);
    background: rgba(0, 0, 0, 0.35);
    color: var(--text-primary);
    font-size: 12px;
  }
  .dg-count {
    font-size: 11px;
    color: #8899aa;
    font-family: ui-monospace, monospace;
  }
  .dg-scroll {
    flex: 1;
    overflow: auto;
    min-height: 0;
  }
  .dg-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }
  .dg-table th {
    position: sticky;
    top: 0;
    background: #0f1a2e;
    text-align: left;
    padding: 8px 10px;
    color: var(--accent);
    font-weight: 600;
    border-bottom: 1px solid var(--glass-border);
    z-index: 1;
  }
  .dg-sort {
    background: none;
    border: none;
    color: inherit;
    font: inherit;
    cursor: pointer;
    padding: 0;
  }
  .dg-table td {
    padding: 7px 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    vertical-align: top;
  }
  .dg-table tbody tr {
    cursor: pointer;
  }
  .dg-table tbody tr:hover {
    background: rgba(0, 212, 255, 0.06);
  }
  .dg-table tbody tr.selected {
    background: rgba(0, 212, 255, 0.12);
    outline: 1px solid var(--accent);
  }
  .dg-empty {
    text-align: center;
    padding: 24px;
    color: #8899aa;
  }
  .dg-detail {
    padding: 12px 14px;
    border-top: 1px solid var(--glass-border);
    font-size: 12px;
    max-height: 220px;
    overflow: auto;
  }
  .dg-detail strong {
    display: block;
    margin-bottom: 8px;
    color: var(--accent);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
</style>
