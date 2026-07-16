<script>
  import { onMount } from "svelte";
  import AdvisorPanel from "./AdvisorPanel.svelte";
  import DataGrid from "./DataGrid.svelte";
  import { sortTaskRows } from "./lib/taskSort.js";
  import {
    countBySliders,
    filterBySliders,
    isTaskUnassigned,
    suggestSliderState,
  } from "./lib/taskFilters.js";

  let {
    platforms = [],
    taskRows = [],
    advisorSuggestions = [],
    omsAiServices = [],
    omsAiSummary = {},
    harnessMode = false,
    focusTaskId = null,
    onSelectEntity = () => {},
    onAssignTask = async () => {},
    rfDisplayUrl = import.meta.env.VITE_RF_DISPLAY_URL || "http://localhost:8082",
  } = $props();

  let selectedId = $state(null);
  let filterTst = $state(false);
  let filterHighPriority = $state(false);
  let lastAutoKey = $state("");
  let lastFocusTaskId = $state(null);
  let assignArmed = $state(false);
  let assignPlatformId = $state(null);
  let showAlternates = $state(false);
  let sending = $state(false);
  let sendError = $state("");
  let platformsOpen = $state(true);
  let alertsOpen = $state(true);

  onMount(() => {
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 768px)").matches) {
      platformsOpen = false;
      alertsOpen = false;
    }
  });

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

  let sortedRows = $derived.by(() => sortTaskRows(taskRows));
  let sliderCounts = $derived(countBySliders(sortedRows));
  let rows = $derived.by(() =>
    filterBySliders(sortedRows, { tst: filterTst, highPriority: filterHighPriority })
  );
  let platformList = $derived(platforms);
  let tstAlerts = $derived(sortedRows.filter((r) => r.is_time_sensitive && r.lifecycle_state !== "EXECUTED"));

  $effect(() => {
    if (focusTaskId) return;
    if (!taskRows.length) return;
    const key = `${harnessMode}:${taskRows.map((t) => t.task_id).join(",")}`;
    if (key === lastAutoKey) return;
    lastAutoKey = key;
    const suggested = suggestSliderState(sortTaskRows(taskRows), { harnessMode });
    filterTst = suggested.tst;
    filterHighPriority = suggested.highPriority;
  });

  $effect(() => {
    if (!focusTaskId || focusTaskId === lastFocusTaskId) return;
    lastFocusTaskId = focusTaskId;
    selectedId = focusTaskId;
    const row = taskRows.find((t) => t.task_id === focusTaskId);
    if (row?.is_time_sensitive) {
      filterTst = true;
      filterHighPriority = false;
    } else if (isTaskUnassigned(row || {})) {
      filterTst = false;
      filterHighPriority = true;
    } else {
      filterTst = false;
      filterHighPriority = false;
    }
  });

  let selectedRow = $derived(taskRows.find((r) => r.task_id === selectedId) || null);

  $effect(() => {
    const row = selectedRow;
    assignArmed = false;
    showAlternates = false;
    sendError = "";
    if (!row || !isTaskUnassigned(row)) {
      assignPlatformId = null;
      return;
    }
    assignPlatformId =
      row.recommended_platform_id ||
      row.allocation_candidates?.[0]?.platform_id ||
      null;
  });

  let candidateList = $derived.by(() => {
    const row = selectedRow;
    if (!row) return [];
    const seen = new Set();
    const list = [];
    for (const c of row.allocation_candidates || []) {
      if (!c?.platform_id || seen.has(c.platform_id)) continue;
      seen.add(c.platform_id);
      list.push({
        platform_id: c.platform_id,
        callsign: c.callsign || c.platform_id,
        role: c.role || row.role || "",
        cost_nm: c.cost_nm,
        reason: c.reason || "",
        recommended: c.platform_id === row.recommended_platform_id,
      });
    }
    if (row.recommended_platform_id && !seen.has(row.recommended_platform_id)) {
      list.unshift({
        platform_id: row.recommended_platform_id,
        callsign: row.recommended_callsign || row.recommended_platform_id,
        role: row.role || "",
        cost_nm: row.cost_nm,
        reason: "Recommended",
        recommended: true,
      });
    }
    return list;
  });

  let primaryCandidate = $derived(
    candidateList.find((c) => c.platform_id === assignPlatformId) || candidateList[0] || null
  );
  let alternateCandidates = $derived(
    candidateList.filter((c) => c.platform_id !== primaryCandidate?.platform_id)
  );
  let primaryPlatform = $derived(
    platformList.find((p) => p.platform_id === primaryCandidate?.platform_id) || null
  );

  let showAssignPanel = $derived(
    Boolean(selectedRow && isTaskUnassigned(selectedRow) && primaryCandidate)
  );
  let showAssignedBanner = $derived(
    Boolean(selectedRow && !isTaskUnassigned(selectedRow))
  );

  let recommendedPlatformIds = $derived.by(() => {
    const ids = new Set();
    const row = selectedRow || taskRows.find((r) => r.task_id === focusTaskId);
    if (!row) return ids;
    if (row.recommended_platform_id) ids.add(row.recommended_platform_id);
    for (const c of row.allocation_candidates || []) {
      if (c.platform_id) ids.add(c.platform_id);
    }
    if (row.assigned_platform_id) ids.add(row.assigned_platform_id);
    return ids;
  });

  function allocationLabel(row) {
    if (row.assigned_platform_id && row.platform_callsign) {
      return `Assigned · ${row.platform_callsign}`;
    }
    if (row.recommended_callsign || row.recommended_platform_id) {
      const top = (row.allocation_candidates || [])[0];
      const cost = top?.cost_nm != null ? ` · ${top.cost_nm} nm` : "";
      const role = top?.role || row.role || "";
      return `Recommend · ${row.recommended_callsign || row.recommended_platform_id}${role ? ` (${role}${cost})` : cost}`;
    }
    return "No platform candidate";
  }

  function pickAlternate(c) {
    assignPlatformId = c.platform_id;
    assignArmed = false;
    showAlternates = false;
  }

  async function sendAssignment() {
    if (!selectedRow || !primaryCandidate || !assignArmed || sending) return;
    sending = true;
    sendError = "";
    try {
      await onAssignTask({
        task_id: selectedRow.task_id,
        platform_id: primaryCandidate.platform_id,
        callsign: primaryCandidate.callsign,
      });
      selectedId = null;
      assignArmed = false;
      assignPlatformId = null;
    } catch (err) {
      sendError = err?.message || String(err);
    } finally {
      sending = false;
    }
  }

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
      key: "recommended_callsign",
      label: "Allocate",
      width: "120px",
      render: (r) => {
        if (r.assigned_platform_id && r.platform_callsign) return r.platform_callsign;
        if (r.recommended_callsign) return `→ ${r.recommended_callsign}`;
        return "—";
      },
    },
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
    {omsAiServices}
    {omsAiSummary}
    {onSelectEntity}
    onAccept={async () => {}}
  />
  <div class="tasking-header">
    <h2>Task queue</h2>
    <div class="queue-toolbar">
      <span class="queue-meta">{rows.length} in queue · {sortedRows.length} total</span>
      <div class="filter-sliders" role="group" aria-label="Task queue filters">
        <label class="slider-toggle" class:on={filterTst} title="Show only time-sensitive tasks">
          <span class="slider-label">TST <em>{sliderCounts.tst}</em></span>
          <span class="slider-control">
            <input type="checkbox" bind:checked={filterTst} />
            <span class="slider-track" aria-hidden="true"><span class="slider-thumb"></span></span>
          </span>
        </label>
        <label class="slider-toggle" class:on={filterHighPriority} title="Show high-priority unassigned tasks">
          <span class="slider-label">High Priority <em>{sliderCounts.highPriority}</em></span>
          <span class="slider-control">
            <input type="checkbox" bind:checked={filterHighPriority} />
            <span class="slider-track" aria-hidden="true"><span class="slider-thumb"></span></span>
          </span>
        </label>
      </div>
    </div>
    {#if tstAlerts.length > 0}
      <div class="tst-alert-strip" class:collapsed={!alertsOpen} role="alert">
        <button
          type="button"
          class="tst-alert-toggle"
          aria-expanded={alertsOpen}
          onclick={() => (alertsOpen = !alertsOpen)}
        >
          <span class="caret">{alertsOpen ? "▾" : "▸"}</span>
          {tstAlerts.length} time-sensitive alert{tstAlerts.length === 1 ? "" : "s"}
          <span class="tst-alert-hint">tap to select · not the filter</span>
        </button>
        {#if alertsOpen}
          <div class="tst-alert-chips">
            {#each tstAlerts as t (t.task_id)}
              <button type="button" class="tst-chip" onclick={() => (selectedId = t.task_id)}>
                {t.target_name} ({t.role}) · {t.tst_minutes_remaining ?? "?"}m
                {#if !isTaskUnassigned(t)}
                  <span class="chip-state">assigned</span>
                {/if}
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {/if}
  </div>
  <div class="tasking-body">
    <div class="platforms-col" class:collapsed={!platformsOpen}>
      <button
        type="button"
        class="platforms-toggle"
        aria-expanded={platformsOpen}
        onclick={() => (platformsOpen = !platformsOpen)}
      >
        <span class="caret">{platformsOpen ? "▾" : "▸"}</span>
        OMS platforms ({platformList.length})
      </button>
      {#if platformsOpen}
      <h3 class="platforms-heading">OMS platforms ({platformList.length})</h3>
      {#if selectedRow}
        <p class="alloc-banner" class:open={!selectedRow.assigned_platform_id}>
          {allocationLabel(selectedRow)}
        </p>
      {/if}
      {#each platformList as plat (plat.platform_id)}
        <div
          class="plat-card"
          class:tasked={plat.active_task_id}
          class:recommended={recommendedPlatformIds.has(plat.platform_id)}
          class:primary={selectedRow?.recommended_platform_id === plat.platform_id || selectedRow?.assigned_platform_id === plat.platform_id || assignPlatformId === plat.platform_id}
        >
          <strong>{plat.callsign}</strong> · {plat.platform_type}
          {#if plat.operational_role}
            <span class="role-tag">{plat.operational_role}</span>
          {/if}
          {#if selectedRow?.recommended_platform_id === plat.platform_id && !selectedRow?.assigned_platform_id}
            <span class="alloc-tag">Recommended</span>
          {/if}
          {#if selectedRow?.assigned_platform_id === plat.platform_id}
            <span class="alloc-tag assigned">Assigned</span>
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
      {/if}
    </div>
    <div class="tasks-col" class:has-assign={showAssignPanel}>
      <DataGrid
        {rows}
        {columns}
        rowKey="task_id"
        bind:selectedId
        searchPlaceholder="Search tasks, targets, platforms…"
        emptyMessage={rows.length === 0
          ? "No tasks match current filters — try toggling TST / High Priority"
          : "No tasks match search"}
        detailTitle="Task lifecycle"
      >
        {#snippet children(row)}
          <div class="task-detail">
            <p><span class="lbl">Target</span> {row.target_name} (<code>{row.target_entity_id}</code>)</p>
            <p><span class="lbl">Allocation</span> {allocationLabel(row)}</p>
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

  {#if showAssignPanel}
    <div class="assign-panel" aria-label="Assign selected task to platform">
      <div class="assign-head">
        <span class="assign-task">{selectedRow.task_id}</span>
        <span class="assign-arrow">→</span>
        <span class="assign-target">{selectedRow.target_name}</span>
        <span class="assign-role">{selectedRow.role}</span>
      </div>
      <div class="assign-platform-box">
        <div class="assign-platform-info">
          <strong>{primaryCandidate.callsign}</strong>
          <span class="dim">
            {primaryPlatform?.platform_type || primaryCandidate.role || "platform"}
            {#if primaryCandidate.cost_nm != null}· {primaryCandidate.cost_nm} nm{/if}
            {#if primaryCandidate.recommended}· recommended{/if}
          </span>
          {#if primaryCandidate.reason}
            <span class="reason">{primaryCandidate.reason}</span>
          {/if}
        </div>
        <label class="arm-slider" class:on={assignArmed} title="Arm send — slide on to enable Send">
          <span class="arm-lbl">{assignArmed ? "Armed" : "Arm"}</span>
          <span class="slider-control">
            <input type="checkbox" bind:checked={assignArmed} />
            <span class="slider-track" aria-hidden="true"><span class="slider-thumb"></span></span>
          </span>
        </label>
        <button
          type="button"
          class="send-btn"
          disabled={!assignArmed || sending}
          onclick={sendAssignment}
        >
          {sending ? "Sending…" : "Send"}
        </button>
      </div>
      {#if sendError}
        <p class="send-error">{sendError}</p>
      {/if}
      {#if alternateCandidates.length}
        <button
          type="button"
          class="alt-caret"
          class:open={showAlternates}
          aria-expanded={showAlternates}
          onclick={() => (showAlternates = !showAlternates)}
        >
          <span class="caret">{showAlternates ? "▾" : "▸"}</span>
          Other platforms nearby ({alternateCandidates.length})
        </button>
        {#if showAlternates}
          <ul class="alt-list">
            {#each alternateCandidates as c (c.platform_id)}
              <li>
                <button type="button" class="alt-item" onclick={() => pickAlternate(c)}>
                  <strong>{c.callsign}</strong>
                  <span class="dim">
                    {#if c.role}{c.role}{/if}
                    {#if c.cost_nm != null}· {c.cost_nm} nm{/if}
                    {#if c.reason}· {c.reason}{/if}
                  </span>
                </button>
              </li>
            {/each}
          </ul>
        {/if}
      {/if}
    </div>
  {:else if showAssignedBanner}
    <div class="assign-panel assigned-only">
      <span class="dim">Assigned to <strong>{selectedRow.platform_callsign || selectedRow.assigned_platform_id}</strong> · {selectedRow.lifecycle_state}</span>
    </div>
  {/if}
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
    margin: 8px 0 0;
    padding: 6px 8px;
    border-radius: 8px;
    border: 1px solid var(--warn);
    background: rgba(251, 146, 60, 0.12);
    font-size: 11px;
    color: #fdba74;
  }
  .tst-alert-toggle {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 2px 0;
    border: none;
    background: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }
  .tst-alert-hint {
    font-size: 9px;
    color: #a8a29e;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .tst-alert-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
  }
  .tst-chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin: 0;
    padding: 2px 6px;
    border-radius: 4px;
    border: 1px solid rgba(239, 68, 68, 0.35);
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
    font-family: ui-monospace, monospace;
    font-size: 10px;
    cursor: pointer;
  }
  .tst-chip:hover {
    border-color: #fca5a5;
  }
  .chip-state {
    font-size: 8px;
    text-transform: uppercase;
    opacity: 0.8;
  }
  :global(.tst-badge) {
    color: #ef4444;
    font-weight: 700;
    font-size: 10px;
    border: 1px solid #ef4444;
    padding: 1px 4px;
    border-radius: 4px;
  }
  .queue-toolbar {
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
  .filter-sliders {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    width: 100%;
  }
  .slider-toggle,
  .arm-slider {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    user-select: none;
    position: relative;
  }
  .slider-control {
    position: relative;
    display: inline-flex;
    align-items: center;
    flex-shrink: 0;
  }
  .slider-toggle input,
  .arm-slider input {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    opacity: 0;
    cursor: pointer;
    z-index: 2;
  }
  .slider-label {
    font-size: 11px;
    color: #c8e6ff;
    min-width: 7.5rem;
  }
  .slider-label em {
    font-style: normal;
    font-family: ui-monospace, monospace;
    opacity: 0.75;
    margin-left: 2px;
  }
  .slider-track {
    position: relative;
    width: 36px;
    height: 18px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid var(--glass-border);
    transition: background 0.15s ease, border-color 0.15s ease;
    flex-shrink: 0;
    pointer-events: none;
  }
  .slider-thumb {
    position: absolute;
    top: 1px;
    left: 1px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: #94a3b8;
    transition: transform 0.15s ease, background 0.15s ease;
  }
  .slider-toggle.on .slider-track,
  .arm-slider.on .slider-track {
    background: rgba(0, 212, 255, 0.28);
    border-color: var(--accent);
  }
  .slider-toggle.on .slider-thumb,
  .arm-slider.on .slider-thumb {
    transform: translateX(18px);
    background: var(--accent);
  }
  .arm-slider .arm-lbl {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #8899aa;
    min-width: 2.6rem;
  }
  .arm-slider.on .arm-lbl {
    color: var(--accent);
  }
  .platforms-toggle {
    display: none;
  }
  .platforms-heading {
    margin: 0 0 10px;
    font-size: 12px;
    color: var(--accent);
  }
  .caret {
    font-size: 10px;
    width: 1em;
    display: inline-block;
  }
  .tasking-body {
    flex: 1;
    display: grid;
    grid-template-columns: 280px 1fr;
    min-height: 0;
    overflow: hidden;
  }
  .platforms-col {
    border-right: 1px solid var(--glass-border);
    overflow: auto;
    -webkit-overflow-scrolling: touch;
    overscroll-behavior: contain;
    padding: 12px;
    min-height: 0;
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
  .plat-card.recommended {
    border-color: rgba(251, 191, 36, 0.55);
  }
  .plat-card.primary {
    border-color: var(--accent);
    background: rgba(0, 212, 255, 0.08);
    box-shadow: 0 0 0 1px rgba(0, 212, 255, 0.25);
  }
  .alloc-banner {
    margin: 0 0 10px;
    padding: 6px 8px;
    border-radius: 6px;
    border: 1px solid var(--glass-border);
    background: rgba(0, 0, 0, 0.3);
    font-size: 10px;
    color: var(--text-muted);
    line-height: 1.35;
  }
  .alloc-banner.open {
    border-color: rgba(251, 191, 36, 0.45);
    color: #fcd34d;
  }
  .alloc-tag {
    display: inline-block;
    margin-left: 4px;
    padding: 1px 5px;
    border-radius: 4px;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    background: rgba(251, 191, 36, 0.2);
    color: #fcd34d;
  }
  .alloc-tag.assigned {
    background: rgba(0, 212, 255, 0.2);
    color: var(--accent);
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
    height: 100%;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .tasks-col :global(.dg-wrap) {
    flex: 1;
    min-height: 0;
  }
  .tasks-col :global(.dg-table tbody tr) {
    border-left: 3px solid transparent;
  }
  .tasks-col :global(.dg-table tbody tr.selected) {
    border-left-color: var(--accent);
    background: rgba(0, 212, 255, 0.16);
    box-shadow: inset 0 0 0 1px rgba(0, 212, 255, 0.35);
  }
  .assign-panel {
    flex-shrink: 0;
    border-top: 1px solid var(--glass-border);
    background: rgba(8, 16, 28, 0.96);
    padding: 10px 12px 12px;
  }
  .assign-panel.assigned-only {
    padding: 8px 12px;
    font-size: 11px;
  }
  .assign-head {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 6px;
    margin-bottom: 8px;
    font-size: 11px;
  }
  .assign-task {
    font-family: ui-monospace, monospace;
    color: var(--accent);
  }
  .assign-arrow {
    color: #8899aa;
  }
  .assign-target {
    color: #e8f4ff;
    font-weight: 600;
  }
  .assign-role {
    font-size: 10px;
    color: #8899aa;
    text-transform: uppercase;
  }
  .assign-platform-box {
    display: grid;
    grid-template-columns: 1fr auto auto;
    gap: 10px;
    align-items: center;
    padding: 10px 12px;
    border: 1px solid rgba(251, 191, 36, 0.4);
    border-radius: 8px;
    background: rgba(251, 191, 36, 0.06);
  }
  .assign-platform-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    font-size: 12px;
  }
  .assign-platform-info .reason {
    font-size: 10px;
    color: #fcd34d;
  }
  .send-btn {
    padding: 8px 14px;
    border-radius: 6px;
    border: 1px solid var(--accent);
    background: rgba(0, 212, 255, 0.2);
    color: #fff;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    cursor: pointer;
  }
  .send-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }
  .send-btn:not(:disabled):hover {
    background: rgba(0, 212, 255, 0.35);
  }
  .send-error {
    margin: 6px 0 0;
    font-size: 11px;
    color: #fca5a5;
  }
  .alt-caret {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 8px;
    padding: 4px 0;
    border: none;
    background: none;
    color: #8899aa;
    font-size: 11px;
    cursor: pointer;
  }
  .alt-caret.open {
    color: #c8e6ff;
  }
  .alt-list {
    list-style: none;
    margin: 4px 0 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .alt-item {
    width: 100%;
    text-align: left;
    padding: 6px 8px;
    border-radius: 6px;
    border: 1px solid var(--glass-border);
    background: rgba(0, 0, 0, 0.25);
    color: #c8e6ff;
    font-size: 11px;
    cursor: pointer;
  }
  .alt-item:hover {
    border-color: var(--accent);
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

  @media (max-width: 768px) {
    .tasking-header {
      padding: 8px 12px;
      flex-shrink: 0;
    }
    .tasking-header h2 {
      margin-bottom: 4px;
    }
    .tasking-body {
      display: flex;
      flex-direction: column;
      grid-template-columns: none;
      grid-template-rows: none;
      min-height: 0;
    }
    .tasks-col {
      order: 1;
      flex: 1;
      min-height: 0;
      height: auto;
      overflow: hidden;
    }
    .tasks-col.has-assign :global(.dg-detail) {
      display: none;
    }
    .platforms-col {
      order: 2;
      border-right: none;
      border-top: 1px solid var(--glass-border);
      border-bottom: none;
      max-height: none;
      flex: 0 0 auto;
      padding: 8px 12px;
      overflow: hidden;
    }
    .platforms-col.collapsed {
      max-height: none;
      overflow: hidden;
    }
    .platforms-toggle {
      display: flex;
      align-items: center;
      gap: 6px;
      width: 100%;
      padding: 4px 0;
      border: none;
      background: none;
      color: var(--accent);
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
    }
    .platforms-heading {
      display: none;
    }
    .platforms-col.collapsed .plat-card,
    .platforms-col.collapsed .alloc-banner,
    .platforms-col.collapsed .badge {
      display: none;
    }
    .assign-panel {
      border-top: 1px solid rgba(251, 191, 36, 0.45);
      box-shadow: 0 -10px 28px rgba(0, 0, 0, 0.55);
      padding-bottom: max(12px, env(safe-area-inset-bottom));
      z-index: 5;
    }
    .assign-platform-box {
      grid-template-columns: 1fr;
    }
    .send-btn {
      width: 100%;
      min-height: 44px;
    }
    .arm-slider {
      justify-content: space-between;
      width: 100%;
      min-height: 40px;
    }
    .slider-toggle {
      min-height: 36px;
      width: 100%;
      justify-content: space-between;
      padding: 4px 0;
    }
    .filter-sliders {
      flex-direction: column;
      gap: 2px;
    }
  }
</style>
