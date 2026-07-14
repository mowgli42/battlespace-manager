<script>
  /** Impacted routes from uci.route.threat (battlespace-manager#14 slice 1). */

  let {
    routeThreats = [],
    selectedRouteName = null,
    selectedEntityId = null,
    onSelect = () => {},
  } = $props();

  let sorted = $derived.by(() =>
    [...routeThreats].sort(
      (a, b) => Number(a.closest_approach_nm ?? 1e9) - Number(b.closest_approach_nm ?? 1e9)
    )
  );

  function bandLabel(nm) {
    const d = Number(nm);
    if (Number.isNaN(d)) return "—";
    if (d <= 50) return "STRIKE";
    if (d <= 100) return "EJ";
    if (d <= 160) return "JAM";
    return "OUT";
  }

  function bandClass(nm) {
    return `band-${bandLabel(nm).toLowerCase()}`;
  }

  function platforms(row) {
    const ids = row.platform_ids || [];
    return ids.length ? ids.join(", ") : "—";
  }
</script>

<section class="route-threat-panel" aria-label="Impacted routes">
  <header>
    <h2>Impacted routes</h2>
    <p class="hint">
      {sorted.length
        ? `${sorted.length} within 160 nm · sorted closest first · bands Strike ≤50 / EJ ≤100 / Jam ≤160`
        : "No route threats on bus — waiting for uci.route.threat"}
    </p>
  </header>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Route</th>
          <th>Platforms</th>
          <th>Closest</th>
          <th>Band</th>
          <th>Severity</th>
          <th>Threat</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {#each sorted as row (row.assessment_id || `${row.route_name}-${row.threat_entity_id}`)}
          <tr
            class:selected={selectedRouteName === row.route_name || selectedEntityId === row.threat_entity_id}
            class:critical={(row.severity || "").toUpperCase() === "CRITICAL"}
            class:high={(row.severity || "").toUpperCase() === "HIGH"}
          >
            <td>
              <button type="button" onclick={() => onSelect(row)}>
                <strong>{row.route_name || "—"}</strong>
              </button>
            </td>
            <td>{platforms(row)}</td>
            <td class="num">{row.closest_approach_nm != null ? `${Number(row.closest_approach_nm).toFixed(1)} nm` : "—"}</td>
            <td><span class="band {bandClass(row.closest_approach_nm)}">{bandLabel(row.closest_approach_nm)}</span></td>
            <td>{row.severity || "—"}</td>
            <td>
              <button type="button" class="linkish" onclick={() => onSelect(row)}>
                {row.threat_entity_id || "—"}
              </button>
            </td>
            <td>
              {#if (row.task_ids || []).length}
                <span class="badge tasked">{row.task_ids.length} task{(row.task_ids.length === 1) ? "" : "s"}</span>
              {:else}
                <span class="badge open">open</span>
              {/if}
            </td>
          </tr>
        {:else}
          <tr class="empty"><td colspan="7">Queue clear — no impacted routes</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<style>
  .route-threat-panel {
    display: flex;
    flex-direction: column;
    min-height: 0;
    height: 100%;
    padding: 12px 14px;
    background: rgba(6, 12, 24, 0.92);
  }
  header h2 {
    margin: 0 0 4px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent, #00d4ff);
  }
  .hint {
    margin: 0 0 10px;
    font-size: 10px;
    color: var(--text-muted, #94a3b8);
    line-height: 1.35;
  }
  .table-wrap {
    overflow: auto;
    min-height: 0;
    border: 1px solid var(--glass-border, rgba(148, 163, 184, 0.2));
    border-radius: 8px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }
  th {
    text-align: left;
    padding: 8px 10px;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted, #94a3b8);
    background: rgba(15, 23, 42, 0.9);
    position: sticky;
    top: 0;
  }
  td {
    padding: 8px 10px;
    border-top: 1px solid rgba(148, 163, 184, 0.12);
    color: var(--text-primary, #e2e8f0);
    vertical-align: middle;
  }
  tr.selected td {
    background: rgba(0, 212, 255, 0.1);
  }
  tr.critical td {
    box-shadow: inset 3px 0 0 #ef4444;
  }
  tr.high td {
    box-shadow: inset 3px 0 0 #f97316;
  }
  button {
    background: none;
    border: none;
    color: inherit;
    padding: 0;
    cursor: pointer;
    text-align: left;
  }
  button:hover strong,
  .linkish:hover {
    color: var(--accent, #00d4ff);
  }
  .num {
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }
  .band {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.04em;
    border: 1px solid currentColor;
  }
  .band-strike {
    color: #ef4444;
    background: rgba(239, 68, 68, 0.15);
  }
  .band-ej {
    color: #f97316;
    background: rgba(249, 115, 22, 0.15);
  }
  .band-jam {
    color: #a78bfa;
    background: rgba(167, 139, 250, 0.15);
  }
  .band-out {
    color: #94a3b8;
  }
  .badge {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 4px;
    border: 1px solid rgba(148, 163, 184, 0.35);
  }
  .badge.tasked {
    color: #4ade80;
    border-color: #4ade80;
  }
  .badge.open {
    color: #fbbf24;
    border-color: #fbbf24;
  }
  tr.empty td {
    color: var(--text-muted, #94a3b8);
    text-align: center;
    padding: 24px;
  }
</style>
