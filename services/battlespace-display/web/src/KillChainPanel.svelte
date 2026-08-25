<script>
  import TargetImagery from "./TargetImagery.svelte";

  let {
    picture = {},
    selectedEntityId = $bindable(null),
    phaseFilter = $bindable(null),
    onMoveTask = () => {},
  } = $props();

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
  let platforms = $derived(picture.platforms || picture.coalition_platforms || []);
  let taskRows = $derived(picture.task_rows || picture.caoc_tasks || []);

  let sel = $derived(resolveSelection(targets, taskRows, selectedEntityId));

  let board = $derived.by(() => {
    const cols = Object.fromEntries(F2T2EA.map((ph) => [ph, []]));
    for (const t of targets) {
      const ph = F2T2EA.includes(t.phase) ? t.phase : "Find";
      cols[ph].push(t);
    }
    if (sel && !targets.some((t) => t.target_id === sel.target_id)) {
      const ph = F2T2EA.includes(sel.phase) ? sel.phase : "Target";
      cols[ph] = [sel, ...cols[ph]];
    }
    return F2T2EA.map((phase) => ({ phase, items: cols[phase] }));
  });

  let assignedPlatform = $derived.by(() => {
    if (!sel?.assigned_platform_id) return null;
    return platforms.find((p) => p.platform_id === sel.assigned_platform_id) || null;
  });

  let assignedTaskRow = $derived.by(() => {
    if (!sel) return null;
    if (sel.task_id) return taskRows.find((r) => r.task_id === sel.task_id) || null;
    return taskRows.find((r) => r.target_entity_id === sel.target_id) || null;
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
    if (row.phase) phaseFilter = row.phase;
  }

  function clearSelection() {
    selectedEntityId = null;
  }

  function taskIdFor(row) {
    if (row?.task_id) return row.task_id;
    if (sel && isSelected(row)) return assignedTaskRow?.task_id || sel.task_id || "";
    return "";
  }

  function openForAssign(row, toPhase) {
    if (!row) return;
    selectTarget(row);
    onMoveTask({
      task_id: taskIdFor(row),
      entity_id: row.target_id,
      from_phase: row.phase,
      to_phase: toPhase || row.phase,
    });
  }

  function requestMove(row, toPhase) {
    if (!row || !toPhase || toPhase === row.phase) {
      selectTarget(row);
      return;
    }
    openForAssign(row, toPhase);
  }

  function onDragStart(e, row) {
    selectTarget(row);
    e.dataTransfer?.setData("text/plain", row.target_id);
    e.dataTransfer.effectAllowed = "move";
  }

  function onDragOver(e) {
    e.preventDefault();
    if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
  }

  function onDropColumn(e, phase) {
    e.preventDefault();
    if (sel) requestMove(sel, phase);
  }

  function isSelected(row) {
    if (!sel) return false;
    return row.target_id === sel.target_id || (row.task_id && row.task_id === sel.task_id);
  }

  function resolveSelection(fkcm, tasks, id) {
    if (!id) return null;
    const direct = fkcm.find(
      (t) => t.target_id === id || t.task_id === id || t.track_id === id
    );
    if (direct) return direct;
    const task = tasks.find((t) => t.task_id === id || t.target_entity_id === id);
    if (!task) return null;
    const viaTask = fkcm.find(
      (t) => t.task_id === task.task_id || t.target_id === task.target_entity_id
    );
    if (viaTask) return viaTask;
    const phase = F2T2EA.includes(task.kill_chain_phase) ? task.kill_chain_phase : "Target";
    return {
      target_id: task.target_entity_id || task.task_id,
      target_name: task.target_name || task.target_entity_id || task.task_id,
      phase,
      phase_color: PHASE_COLORS[phase],
      classification: "Unknown",
      latitude: task.latitude,
      longitude: task.longitude,
      altitude_feet: 0,
      task_id: task.task_id,
      assigned_task: `${task.role || "TASK"} (${task.task_id})`,
      task_status: task.lifecycle_state || task.status || "—",
      assigned_platform_id: task.assigned_platform_id || task.platform_id || "",
      platform_type: task.target_type || "",
      domain: "",
      bda_status: "—",
      notes: task.notes || "",
      flags: [],
      last_updated_label: "—",
    };
  }
</script>

<div class="fkcm-layout">
  <header class="fkcm-toolbar">
    <div class="toolbar-top">
      <h2>F2T2EA</h2>
      <span class="hint">
        {targets.length} task{targets.length === 1 ? "" : "s"} · drag a card to another state to assign a platform
      </span>
    </div>
  </header>

  <div class="fkcm-body" class:has-detail={!!sel}>
    <section class="kanban" aria-label="F2T2EA kanban">
      {#each board as col (col.phase)}
        <div
          class="kanban-col"
          class:drop-ready={sel && sel.phase !== col.phase}
          class:emphasized={phaseFilter === col.phase}
          style="--ph-color: {PHASE_COLORS[col.phase]}"
          role="group"
          aria-label="{col.phase} column"
          ondragover={onDragOver}
          ondrop={(e) => onDropColumn(e, col.phase)}
        >
          <header class="kanban-head">
            <span class="ph-name">{col.phase}</span>
            <span class="ph-count">{col.items.length}</span>
          </header>
          {#if sel && sel.phase !== col.phase}
            <button type="button" class="move-here" onclick={() => requestMove(sel, col.phase)}>
              Move here to assign
            </button>
          {/if}
          <ul class="kanban-cards">
            {#each col.items as row (row.target_id)}
              <li>
                <button
                  type="button"
                  class="target-card"
                  class:selected={isSelected(row)}
                  draggable="true"
                  ondragstart={(e) => onDragStart(e, row)}
                  onclick={() => selectTarget(row)}
                >
                  <div class="card-head">
                    <strong>{row.target_name}</strong>
                    <span class="class">{row.classification}</span>
                  </div>
                  <div class="card-meta">
                    <span>{row.platform_type || row.domain}</span>
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
        </div>
      {/each}
    </section>

    {#if sel}
      <section class="target-detail" aria-label="Target detail">
        <div class="detail-header">
          <div>
            <h3>{sel.target_name}</h3>
            <p class="sub">{sel.classification} · {sel.platform_type || sel.domain} · {sel.phase}</p>
          </div>
          <div class="detail-actions">
            <button
              type="button"
              class="details-btn"
              onclick={() => openForAssign(sel, F2T2EA[Math.min(F2T2EA.indexOf(sel.phase) + 1, F2T2EA.length - 1)])}
            >
              Assign platform to move
            </button>
            <button type="button" class="close-btn" onclick={clearSelection} title="Close detail">✕</button>
          </div>
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
              {#if assignedTaskRow}
                <strong>{assignedTaskRow.role || "TASK"}</strong>
                <span class="status-pill">{assignedTaskRow.lifecycle_state || assignedTaskRow.status || "—"}</span>
                <span class="dim">{assignedTaskRow.task_id}</span>
                {#if assignedTaskRow.is_time_sensitive}
                  <span class="dim">TST {assignedTaskRow.tst_minutes_remaining ?? "—"}m</span>
                {/if}
                {#if assignedTaskRow.required_weapon}
                  <span class="dim">{assignedTaskRow.required_weapon}</span>
                {/if}
              {:else if sel.assigned_task && sel.assigned_task !== "—"}
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
          <span class="map-label">Task snapshot</span>
          <TargetImagery target={sel} task={assignedTaskRow} />
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
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .kanban {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: repeat(6, minmax(140px, 1fr));
    gap: 8px;
    padding: 10px 12px;
    overflow: auto;
  }
  .kanban-col {
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
    border-radius: 8px;
    border: 1px solid color-mix(in srgb, var(--ph-color) 45%, var(--glass-border));
    background: rgba(8, 14, 28, 0.85);
  }
  .kanban-col.emphasized {
    box-shadow: inset 0 0 0 1px var(--ph-color);
  }
  .kanban-col.drop-ready {
    border-style: dashed;
    background: color-mix(in srgb, var(--ph-color) 8%, transparent);
  }
  .kanban-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 10px;
    border-bottom: 1px solid color-mix(in srgb, var(--ph-color) 40%, transparent);
    color: var(--ph-color);
    font-size: 11px;
    font-weight: 700;
    flex-shrink: 0;
  }
  .move-here {
    margin: 6px 8px 0;
    padding: 5px 8px;
    border-radius: 4px;
    border: 1px dashed var(--ph-color);
    background: color-mix(in srgb, var(--ph-color) 12%, transparent);
    color: var(--ph-color);
    font-size: 10px;
    cursor: pointer;
  }
  .kanban-cards {
    list-style: none;
    margin: 0;
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow-y: auto;
    min-height: 0;
    flex: 1;
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
    max-height: 46%;
    overflow: auto;
    padding: 12px 14px;
    gap: 12px;
    border-top: 1px solid var(--glass-border);
  }
  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
  }
  .detail-actions {
    display: flex;
    gap: 6px;
    align-items: center;
  }
  .details-btn {
    padding: 5px 10px;
    border-radius: 4px;
    border: 1px solid var(--accent);
    background: rgba(0, 212, 255, 0.12);
    color: var(--accent);
    font-size: 10px;
    cursor: pointer;
    white-space: nowrap;
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

  @media (max-width: 768px) {
    .kanban {
      grid-template-columns: repeat(2, minmax(140px, 1fr));
    }
    .target-detail {
      max-height: 50%;
    }
  }
</style>
