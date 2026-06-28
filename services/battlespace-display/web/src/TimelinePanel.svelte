<script>
  let {
    picture = {},
    onSelectEntity = () => {},
    onOpenDecisions = () => {},
  } = $props();

  let filter = $state("all");

  let tv = $derived(picture.timeline_view || {});
  let sim = $derived(tv.sim_minutes ?? picture.sim_minutes ?? 0);
  let horizon = $derived(tv.horizon_minutes ?? 90);
  let items = $derived(tv.items || []);

  let filtered = $derived.by(() => {
    if (filter === "scenario") return items.filter((i) => i.kind === "scenario");
    if (filter === "tasks") return items.filter((i) => i.kind === "task");
    if (filter === "upcoming") {
      return items.filter((i) => i.status !== "past" && i.status !== "active");
    }
    return items;
  });

  function fmtSim(m) {
    const mins = Math.floor(m);
    const secs = Math.round((m % 1) * 60);
    return `T+${mins}:${String(secs).padStart(2, "0")}`;
  }

  function offsetPct(offset) {
    const max = Math.max(horizon, sim + 5, 1);
    return Math.min(100, Math.max(0, (offset / max) * 100));
  }

  function nowPct() {
    return offsetPct(sim);
  }

  function onItemClick(item) {
    if (item.entity_id) onSelectEntity(item.entity_id);
    if (item.kind === "task") onOpenDecisions();
  }

  const KIND_LABEL = { scenario: "Scenario", task: "Task" };
  const STATUS_LABEL = {
    past: "Complete",
    imminent: "Imminent",
    future: "Scheduled",
    open: "Open",
    active: "In progress",
  };
</script>

<div class="timeline-panel">
  <header class="tl-header">
    <div>
      <h2>Mission timeline</h2>
      <p class="tl-sub">
        {tv.upcoming_count ?? 0} upcoming · {tv.scenario_count ?? 0} scenario beats · {tv.task_count ?? 0} open tasks
      </p>
    </div>
    <div class="tl-now" aria-label="Current simulation time">
      <span class="tl-now-lbl">NOW</span>
      <span class="tl-now-val">{fmtSim(sim)}</span>
    </div>
  </header>

  <div class="tl-filters" role="tablist" aria-label="Timeline filters">
    {#each [
      { id: "all", label: "All" },
      { id: "upcoming", label: "Upcoming" },
      { id: "scenario", label: "Scenario" },
      { id: "tasks", label: "Tasks" },
    ] as f}
      <button
        type="button"
        role="tab"
        class:active={filter === f.id}
        aria-selected={filter === f.id}
        onclick={() => (filter = f.id)}
      >
        {f.label}
      </button>
    {/each}
  </div>

  <div class="tl-rail-wrap">
    <div class="tl-axis" aria-hidden="true">
      <div class="tl-now-marker" style="left: {nowPct()}%"></div>
      {#each [0, 15, 30, 45, 60, 75, 90] as tick}
        {#if tick <= horizon}
          <span class="tl-tick" style="left: {offsetPct(tick)}%">{tick}m</span>
        {/if}
      {/each}
    </div>

    <div class="tl-list">
      {#each filtered as item (item.id)}
        <button
          type="button"
          class="tl-card tl-{item.kind} tl-status-{item.status}"
          onclick={() => onItemClick(item)}
          title={item.detail}
        >
          <div class="tl-card-rail">
            <span class="tl-dot"></span>
            <span class="tl-line"></span>
          </div>
          <div class="tl-card-body">
            <div class="tl-card-meta">
              <span class="tl-time">{fmtSim(item.sim_offset)}</span>
              <span class="tl-kind">{KIND_LABEL[item.kind] || item.kind}</span>
              <span class="tl-status">{STATUS_LABEL[item.status] || item.status}</span>
              {#if item.is_tst}
                <span class="tl-tst">TST</span>
              {/if}
            </div>
            <div class="tl-title">{item.title}</div>
            <div class="tl-detail">{item.detail}</div>
          </div>
        </button>
      {:else}
        <p class="tl-empty">No timeline items for this filter.</p>
      {/each}
    </div>
  </div>
</div>

<style>
  .timeline-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    padding: 16px 20px;
    background: rgba(6, 12, 24, 0.98);
    overflow: hidden;
  }

  .tl-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 12px;
    flex-shrink: 0;
  }

  .tl-header h2 {
    margin: 0;
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--accent);
  }

  .tl-sub {
    margin: 4px 0 0;
    font-size: 12px;
    color: var(--text-muted);
  }

  .tl-now {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    padding: 8px 12px;
    border-radius: 8px;
    border: 1px solid var(--accent);
    background: rgba(0, 212, 255, 0.08);
  }

  .tl-now-lbl {
    font-size: 9px;
    letter-spacing: 0.12em;
    color: var(--text-muted);
  }

  .tl-now-val {
    font-family: ui-monospace, monospace;
    font-size: 18px;
    font-weight: 700;
    color: var(--accent);
  }

  .tl-filters {
    display: flex;
    gap: 8px;
    margin-bottom: 14px;
    flex-shrink: 0;
  }

  .tl-filters button {
    padding: 6px 12px;
    border-radius: 6px;
    border: 1px solid var(--glass-border);
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-muted);
    font-size: 11px;
    cursor: pointer;
  }

  .tl-filters button.active {
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(0, 212, 255, 0.12);
  }

  .tl-rail-wrap {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .tl-axis {
    position: relative;
    height: 28px;
    margin-bottom: 8px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    flex-shrink: 0;
  }

  .tl-now-marker {
    position: absolute;
    top: 0;
    bottom: -8px;
    width: 2px;
    background: var(--accent);
    box-shadow: 0 0 8px var(--accent);
    transform: translateX(-50%);
    z-index: 2;
  }

  .tl-now-marker::before {
    content: "NOW";
    position: absolute;
    top: -2px;
    left: 4px;
    font-size: 8px;
    letter-spacing: 0.08em;
    color: var(--accent);
    white-space: nowrap;
  }

  .tl-tick {
    position: absolute;
    bottom: 4px;
    transform: translateX(-50%);
    font-size: 9px;
    color: var(--text-muted);
    font-family: ui-monospace, monospace;
  }

  .tl-list {
    flex: 1;
    overflow-y: auto;
    padding-right: 4px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .tl-card {
    display: flex;
    gap: 12px;
    width: 100%;
    text-align: left;
    padding: 10px 12px;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.03);
    color: var(--text-primary);
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }

  .tl-card:hover {
    border-color: var(--accent);
    background: rgba(0, 212, 255, 0.06);
  }

  .tl-card-rail {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 12px;
    flex-shrink: 0;
    padding-top: 6px;
  }

  .tl-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-muted);
    flex-shrink: 0;
  }

  .tl-line {
    flex: 1;
    width: 2px;
    min-height: 8px;
    background: rgba(255, 255, 255, 0.08);
    margin-top: 4px;
  }

  .tl-card-body {
    flex: 1;
    min-width: 0;
  }

  .tl-card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 4px;
    font-size: 10px;
  }

  .tl-time {
    font-family: ui-monospace, monospace;
    color: var(--accent);
    font-weight: 600;
  }

  .tl-kind {
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-muted);
  }

  .tl-status {
    padding: 1px 6px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.06);
    color: var(--text-muted);
  }

  .tl-tst {
    padding: 1px 6px;
    border-radius: 4px;
    background: rgba(239, 68, 68, 0.2);
    color: #fca5a5;
    font-weight: 700;
  }

  .tl-title {
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 2px;
  }

  .tl-detail {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.4;
  }

  .tl-scenario .tl-dot {
    background: #a78bfa;
  }

  .tl-task .tl-dot {
    background: #f97316;
  }

  .tl-status-past {
    opacity: 0.55;
  }

  .tl-status-imminent {
    border-color: var(--warn);
    box-shadow: inset 0 0 0 1px rgba(251, 191, 36, 0.2);
  }

  .tl-status-imminent .tl-status {
    color: var(--warn);
    border: 1px solid var(--warn);
  }

  .tl-status-future .tl-dot {
    background: transparent;
    border: 2px dashed rgba(255, 255, 255, 0.25);
  }

  .tl-status-active {
    border-color: rgba(34, 197, 94, 0.4);
  }

  .tl-status-active .tl-dot {
    background: var(--ok);
  }

  .tl-empty {
    color: var(--text-muted);
    font-size: 13px;
    padding: 24px;
    text-align: center;
  }
</style>
