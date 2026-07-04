<script>
  import AdvisorPanel from "./AdvisorPanel.svelte";
  import DataGrid from "./DataGrid.svelte";
  import { sortTaskRows } from "./lib/taskSort.js";

  let {
    platforms = [],
    taskRows = [],
    advisorSuggestions = [],
    onSelectEntity = () => {},
    rfDisplayUrl = import.meta.env.VITE_RF_DISPLAY_URL || "http://localhost:8082",
  } = $props();
  let selectedId = $state(null);

  const LIFECYCLE = ["NEW", "QUEUED", "ANALYZING", "ASSIGNMENT", "ACCEPTED", "EXECUTED", "ABORTED"];
  const LC_COLORS = {
    NEW: "#94a3b8",
    ANALYZING: "#eab308",
    ASSIGNMENT: "#f97316",
    ACCEPTED: "#22c55e",
    EXECUTED: "#4ade80",
    ABORTED: "#ef4444",
    QUEUED: "#a78bfa",
  };

  let rows = $derived.by(() => sortTaskRows(taskRows));
  let platformList = $derived(platforms);
  let tstAlerts = $derived(rows.filter((r) => r.is_time_sensitive && r.lifecycle_state !== "EXECUTED"));
  let lifecycleCounts = $derived.by(() => {
    const c = {};
    for (const lc of LIFECYCLE) c[lc] = 0;
    for (const r of rows) {
      const k = r.lifecycle_state || "NEW";
      c[k] = (c[k] || 0) + 1;
    }
    return c;
  });

  const columns = [
    {
      key: "is_time_sensitive",
      label: "TST",
      width: "48px",
      html: (r) =>
        r.is_time_sensitive
          ? `<span class="tst-badge" title="${r.tst_minutes_remaining != null ? r.tst_minutes_remaining + " min" : "TST"}">TST</span>`
          : "—",
    },
    { key: "task_id", label: "Task ID", width: "110px" },
    { key: "target_name", label: "Target", width: "120px" },
    { key: "target_type", label: "Type", width: "90px" },
    { key: "role", label: "Role", width: "70px" },
    { key: "required_weapon", label: "Wpn req", width: "70px", render: (r) => r.required_weapon || "—" },
    { key: "platform_callsign", label: "Platform", width: "90px" },
    {
      key: "lifecycle_state",
      label: "Lifecycle",
      width: "100px",
      html: (r) => {
        const lc = r.lifecycle_state || "NEW";
        const c = LC_COLORS[lc] || "#94a3b8";
        return `<span class="lc-pill" style="color:${c};border-color:${c}">${lc}</span>`;
      },
    },
    { key: "kill_chain_phase", label: "F2T2EA", width: "70px" },
    {
      key: "cost_nm",
      label: "Cost",
      width: "55px",
      render: (r) => (r.cost_nm != null ? `${r.cost_nm} nm` : "—"),
    },
    {
      key: "tst_minutes_remaining",
      label: "TST T-",
      width: "60px",
      render: (r) =>
        r.is_time_sensitive && r.tst_minutes_remaining != null
          ? `${Number(r.tst_minutes_remaining).toFixed(1)}m`
          : "—",
    },
  ];
</script>

<div class="tasking-panel">
  <AdvisorPanel
    {advisorSuggestions}
    {onSelectEntity}
    onAccept={async () => {}}
  />
  <div class="tasking-header">
    <h2>CAOC tasking queue</h2>
    {#if tstAlerts.length > 0}
      <div class="tst-alert-strip" role="alert">
        {tstAlerts.length} time-sensitive target{tstAlerts.length === 1 ? "" : "s"} —
        {#each tstAlerts as t (t.task_id)}
          <span class="tst-chip">{t.target_name} ({t.role}) · {t.tst_minutes_remaining ?? "?"}m</span>
        {/each}
      </div>
    {/if}
    <div class="lifecycle-bar">
      <span class="queue-meta">{rows.length} tasks · {platformList.length} OMS platforms</span>
      {#each LIFECYCLE as lc (lc)}
        <span title="{lc}">
          <em style="background:{LC_COLORS[lc]}"></em>
          {lc} <strong>{lifecycleCounts[lc] ?? 0}</strong>
        </span>
      {/each}
    </div>
  </div>
  <div class="tasking-body">
    <div class="platforms-col">
      <h3>OMS platforms ({platformList.length})</h3>
      {#each platformList as plat (plat.platform_id)}
        <div class="plat-card" class:tasked={plat.active_task_id}>
          <strong>{plat.callsign}</strong> · {plat.platform_type}
          {#if plat.operational_role}
            <span class="role-tag">{plat.operational_role}</span>
          {/if}
          <br />
          <span class="dim">
            {plat.route_name || "—"} · Fuel {Math.round(plat.fuel_percent)}%
            {#if plat.weapons_remaining > 0}· WPN {plat.weapons_remaining}{/if}
          </span>
          {#if plat.active_task_id}
            <div class="task-link">
              <span class="lbl">Task</span> {plat.active_task_id}
              {#if plat.task_role}· {plat.task_role}{/if}
              {#if plat.kill_chain_phase}· F2T2EA {plat.kill_chain_phase}{/if}
            </div>
          {/if}
          {#if plat.subsystems && Object.keys(plat.subsystems).length}
            <div class="subs">
              {#each Object.entries(plat.subsystems) as [name, status] (name)}
                <span
                  class="sub"
                  class:off={status === "OFF" || status === "N/A"}
                  class:comm={name.includes(":")}
                  class:unavailable={status === "UNAVAILABLE" || status === "CONFLICTED"}
                  class:metered={status === "METERED_ACTIVE"}
                  class:reserved={status === "RESERVED" || status === "REQUESTED"}
                  title={name}
                >{name}: {status}</span>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
      {#if platformList.length === 0}
        <p class="badge">Platform telemetry loads from coalition fleet — check API connection</p>
      {/if}
    </div>
    <div class="tasks-col">
      <DataGrid
        {rows}
        {columns}
        rowKey="task_id"
        bind:selectedId
        searchPlaceholder="Search tasks, targets, platforms…"
        emptyMessage={rows.length === 0
          ? "ATO tasks appear at T+0; CAOC requests (e.g. SEAD T+20) add TST rows as scenario advances"
          : "No tasks match search"}
        detailTitle="Task lifecycle"
      >
        {#snippet children(row)}
          <div class="task-detail">
            <p><span class="lbl">Target</span> {row.target_name} (<code>{row.target_entity_id}</code>)</p>
            <p><span class="lbl">Notes</span> {row.notes || "—"}</p>
            {#if row.bda_result}<p><span class="lbl">BDA</span> {row.bda_result}</p>{/if}
            <div class="phase-track">
              {#each LIFECYCLE as ph (ph)}
                <span class:on={(row.lifecycle_state || "NEW") === ph}>{ph}</span>
              {/each}
            </div>
            {#if row.history?.length}
              <fieldset>
                <legend>History</legend>
                <ul>
                  {#each row.history as h, hi (`${h.sim_minutes}-${h.state}-${hi}`)}
                    <li>T+{h.sim_minutes} · <strong>{h.state}</strong> — {h.note}</li>
                  {/each}
                </ul>
              </fieldset>
            {/if}
            {#if row.role === "SEAD" || (row.target_type || "").includes("SAM")}
              <p class="rf-crosslink">
                <a
                  href="{rfDisplayUrl}?highlight={encodeURIComponent(row.target_entity_id)}"
                  target="_blank"
                  rel="noopener noreferrer"
                >RF spectrum · highlight {row.target_name}</a>
              </p>
            {/if}
          </div>
        {/snippet}
      </DataGrid>
    </div>
  </div>
</div>

<style>
  .tasking-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    padding: 0;
  }
  .tasking-header {
    padding: 12px 16px;
    border-bottom: 1px solid var(--glass-border);
  }
  .tasking-header h2 {
    margin: 0 0 8px;
    font-size: 14px;
    color: var(--accent);
    text-transform: uppercase;
  }
  .tst-alert-strip {
    margin: 0 0 8px;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--warn);
    background: rgba(251, 146, 60, 0.12);
    font-size: 11px;
    color: #fdba74;
  }
  .tst-chip {
    display: inline-block;
    margin-left: 6px;
    padding: 2px 6px;
    border-radius: 4px;
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
    font-family: ui-monospace, monospace;
  }
  :global(.tst-badge) {
    color: #ef4444;
    font-weight: 700;
    font-size: 10px;
    border: 1px solid #ef4444;
    padding: 1px 4px;
    border-radius: 4px;
  }
  .lifecycle-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    font-size: 10px;
    color: #8899aa;
    align-items: center;
  }
  .queue-meta {
    width: 100%;
    margin-bottom: 4px;
    font-size: 11px;
    color: #c8e6ff;
  }
  .lifecycle-bar span {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .lifecycle-bar em {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    font-style: normal;
  }
  .lifecycle-bar strong {
    color: var(--text-primary);
  }
  .tasking-body {
    flex: 1;
    display: grid;
    grid-template-columns: 280px 1fr;
    min-height: 0;
  }
  .platforms-col {
    border-right: 1px solid var(--glass-border);
    overflow: auto;
    padding: 12px;
  }
  .platforms-col h3 {
    margin: 0 0 10px;
    font-size: 12px;
    color: var(--accent);
  }
  .plat-card {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 8px;
    padding: 8px;
    margin-bottom: 8px;
    font-size: 11px;
  }
  .plat-card.tasked {
    border-color: rgba(0, 212, 255, 0.45);
    box-shadow: 0 0 0 1px rgba(0, 212, 255, 0.15);
  }
  .role-tag {
    display: inline-block;
    margin-left: 4px;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 9px;
    background: rgba(0, 212, 255, 0.15);
    color: var(--accent);
  }
  .task-link {
    margin-top: 4px;
    font-size: 10px;
    color: #c8e6ff;
  }
  .subs {
    display: flex;
    flex-wrap: wrap;
    gap: 3px;
    margin-top: 6px;
  }
  .sub {
    font-size: 8px;
    padding: 2px 4px;
    border-radius: 3px;
    background: rgba(34, 197, 94, 0.15);
    color: #86efac;
  }
  .sub.off {
    background: rgba(100, 116, 139, 0.2);
    color: #94a3b8;
  }
  .sub.comm {
    border: 1px solid rgba(34, 211, 238, 0.25);
  }
  .sub.unavailable {
    background: rgba(255, 75, 75, 0.2);
    color: #fca5a5;
  }
  .sub.metered {
    background: rgba(245, 158, 11, 0.2);
    color: #fcd34d;
  }
  .sub.reserved {
    background: rgba(34, 211, 238, 0.2);
    color: #67e8f9;
  }
  .tasks-col {
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .dim {
    color: #8899aa;
    font-size: 10px;
  }
  .task-detail p {
    margin: 0 0 6px;
  }
  .lbl {
    color: #8899aa;
    font-size: 10px;
    text-transform: uppercase;
    margin-right: 6px;
  }
  .phase-track {
    display: flex;
    gap: 3px;
    margin: 10px 0;
  }
  .phase-track span {
    flex: 1;
    text-align: center;
    font-size: 8px;
    padding: 4px 1px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.06);
    color: #8899aa;
  }
  .phase-track span.on {
    background: rgba(0, 212, 255, 0.3);
    color: #fff;
    font-weight: 600;
  }
  fieldset {
    border: 1px solid var(--glass-border);
    border-radius: 6px;
    margin-top: 8px;
    padding: 8px;
  }
  legend {
    font-size: 10px;
    color: var(--accent);
  }
  ul {
    margin: 0;
    padding-left: 16px;
    font-size: 11px;
  }
  :global(.lc-pill) {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    border: 1px solid;
    font-size: 10px;
    font-weight: 600;
  }
  .rf-crosslink {
    margin: 8px 0 0;
    font-size: 11px;
  }
  .rf-crosslink a {
    color: #38bdf8;
    text-decoration: none;
  }
  .rf-crosslink a:hover {
    text-decoration: underline;
  }
</style>
