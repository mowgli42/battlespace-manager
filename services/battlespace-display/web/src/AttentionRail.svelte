<script>
  import { onMount } from "svelte";

  let { items = [], selectedEntityId = null, onSelect = () => {} } = $props();

  const KIND_META = [
    { kind: "TST", label: "TST", tone: "tst" },
    { kind: "POPUP", label: "POP", tone: "popup" },
    { kind: "TARGET", label: "TGT", tone: "target" },
    { kind: "TASK", label: "TSK", tone: "task" },
    { kind: "CUSTODY", label: "CUS", tone: "custody" },
    { kind: "AGENT", label: "ADV", tone: "agent" },
  ];

  let expanded = $state(true);
  let filterKind = $state(null);

  onMount(() => {
    if (typeof window !== "undefined" && window.matchMedia("(max-width: 768px)").matches) {
      expanded = false;
    }
  });

  let kindCounts = $derived.by(() => {
    const counts = {};
    for (const item of items) {
      const k = item.kind || "OTHER";
      counts[k] = (counts[k] || 0) + 1;
    }
    return counts;
  });

  let kindBubbles = $derived(
    KIND_META.map((m) => ({ ...m, count: kindCounts[m.kind] || 0 })).filter((m) => m.count > 0)
  );

  let visibleItems = $derived(
    filterKind ? items.filter((item) => item.kind === filterKind) : items
  );

  let summary = $derived.by(() => {
    const parts = [];
    if (kindCounts.TST) parts.push(`${kindCounts.TST} time-sensitive`);
    if (kindCounts.POPUP) parts.push(`${kindCounts.POPUP} pop-up`);
    if (kindCounts.TARGET) parts.push(`${kindCounts.TARGET} target`);
    if (kindCounts.TASK) parts.push(`${kindCounts.TASK} task`);
    if (kindCounts.CUSTODY) parts.push(`${kindCounts.CUSTODY} custody`);
    if (kindCounts.AGENT) parts.push(`${kindCounts.AGENT} advisor`);
    return parts.length ? parts.join(" · ") : "No urgent items — monitoring battlespace";
  });

  function openKind(kind) {
    filterKind = kind;
    expanded = true;
  }

  function toggleExpanded() {
    expanded = !expanded;
    if (!expanded) filterKind = null;
  }
</script>

{#if expanded}
  <aside class="attention-rail" aria-label="Operator attention queue">
    <div class="rail-head">
      <div class="rail-title-row">
        <h2>Attention</h2>
        <button
          type="button"
          class="icon-btn"
          onclick={toggleExpanded}
          title="Collapse attention rail"
          aria-label="Collapse attention rail"
        >
          ‹
        </button>
      </div>
      <p class="hint" aria-live="polite">{summary}</p>
      {#if kindBubbles.length}
        <div class="filter-chips" role="toolbar" aria-label="Filter by alert type">
          <button
            type="button"
            class="chip"
            class:active={filterKind == null}
            onclick={() => (filterKind = null)}
          >
            All · {items.length}
          </button>
          {#each kindBubbles as b (b.kind)}
            <button
              type="button"
              class="chip tone-{b.tone}"
              class:active={filterKind === b.kind}
              onclick={() => (filterKind = b.kind)}
            >
              {b.label} · {b.count}
            </button>
          {/each}
        </div>
      {/if}
    </div>
    <ul>
      {#each visibleItems as item, idx (item.id ?? `${item.kind}-${item.entity_id ?? ""}-${idx}`)}
        <li>
          <button
            type="button"
            class:selected={selectedEntityId === item.entity_id}
            class:urgent={item.urgency <= 1}
            class:tst={item.kind === "TST"}
            class:agent={item.kind === "AGENT"}
            onclick={() => onSelect(item)}
          >
            <span class="kind" class:agent-kind={item.kind === "AGENT"} class:tst-kind={item.kind === "TST"}
              >{item.kind}</span
            >
            <strong>{item.title}</strong>
            <span class="detail">
              {item.detail}
              {#if item.minutes_remaining != null && item.kind === "TST"}
                <em class="tst-remaining"> · {item.minutes_remaining.toFixed(1)} min</em>
              {/if}
            </span>
          </button>
        </li>
      {:else}
        <li class="empty">
          {filterKind ? `No ${filterKind} items` : "Queue clear — battlespace nominal"}
        </li>
      {/each}
    </ul>
  </aside>
{:else}
  <aside class="attention-rail collapsed" aria-label="Attention alerts compact">
    <button
      type="button"
      class="icon-btn expand-all"
      onclick={toggleExpanded}
      title="Expand attention rail"
      aria-label="Expand attention rail"
    >
      ›
    </button>
    {#if kindBubbles.length === 0}
      <span class="bubble empty-bubble" title="Queue clear">0</span>
    {:else}
      {#each kindBubbles as b (b.kind)}
        <button
          type="button"
          class="bubble tone-{b.tone}"
          title={`${b.count} ${b.kind} — expand`}
          aria-label={`${b.count} ${b.kind} alerts, expand rail`}
          onclick={() => openKind(b.kind)}
        >
          <span class="bubble-kind">{b.label}</span>
          <span class="bubble-count">{b.count}</span>
        </button>
      {/each}
    {/if}
  </aside>
{/if}

<style>
  .attention-rail {
    width: 240px;
    flex-shrink: 0;
    border-right: 1px solid var(--glass-border);
    background: rgba(6, 12, 24, 0.98);
    padding: 12px;
    overflow-y: auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .attention-rail.collapsed {
    width: 52px;
    padding: 8px 6px;
    align-items: center;
    gap: 8px;
    overflow-x: hidden;
  }

  .rail-head {
    flex-shrink: 0;
  }

  .rail-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 4px;
  }

  h2 {
    margin: 0;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent);
  }

  .icon-btn {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    border: 1px solid var(--glass-border);
    background: rgba(0, 0, 0, 0.35);
    color: var(--text-primary);
    cursor: pointer;
    font-size: 16px;
    line-height: 1;
    padding: 0;
    flex-shrink: 0;
  }

  .icon-btn:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .expand-all {
    margin-bottom: 2px;
  }

  .hint {
    margin: 0 0 8px;
    font-size: 10px;
    color: var(--text-muted);
    line-height: 1.35;
  }

  .filter-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 4px;
  }

  .chip {
    border: 1px solid var(--glass-border);
    background: rgba(0, 0, 0, 0.3);
    color: var(--text-muted);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    padding: 3px 6px;
    border-radius: 999px;
    cursor: pointer;
  }

  .chip:hover,
  .chip.active {
    border-color: var(--accent);
    color: var(--accent);
  }

  .chip.tone-tst.active,
  .chip.tone-tst:hover {
    border-color: #ef4444;
    color: #fca5a5;
  }

  .bubble {
    width: 40px;
    min-height: 40px;
    border-radius: 10px;
    border: 1px solid var(--glass-border);
    background: var(--glass-bg);
    color: var(--text-primary);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1px;
    padding: 4px 2px;
  }

  .bubble:hover {
    border-color: var(--accent);
  }

  .bubble.tone-tst {
    border-color: rgba(239, 68, 68, 0.55);
    background: rgba(239, 68, 68, 0.18);
  }

  .bubble.tone-popup {
    border-color: rgba(251, 191, 36, 0.55);
    background: rgba(251, 191, 36, 0.12);
  }

  .bubble.tone-agent {
    border-color: rgba(196, 181, 253, 0.5);
    background: rgba(167, 139, 250, 0.12);
  }

  .bubble.tone-target {
    border-color: rgba(248, 113, 113, 0.45);
  }

  .bubble-kind {
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: var(--text-muted);
  }

  .bubble.tone-tst .bubble-kind {
    color: #fca5a5;
  }

  .bubble-count {
    font-family: ui-monospace, monospace;
    font-size: 13px;
    font-weight: 700;
    color: var(--accent);
  }

  .bubble.tone-tst .bubble-count {
    color: #fecaca;
  }

  .empty-bubble {
    font-size: 11px;
    color: var(--text-muted);
    cursor: default;
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  li button {
    width: 100%;
    text-align: left;
    padding: 8px;
    margin-bottom: 6px;
    border-radius: 8px;
    border: 1px solid var(--glass-border);
    background: var(--glass-bg);
    color: var(--text-primary);
    cursor: pointer;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  li button:hover {
    border-color: var(--accent);
  }

  li button.selected {
    outline: 1px solid var(--accent);
    background: rgba(0, 212, 255, 0.1);
  }

  li button.urgent {
    border-color: var(--warn);
  }

  li button.tst {
    border-color: #ef4444;
    background: rgba(239, 68, 68, 0.15);
    box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.25);
  }

  .kind.tst-kind {
    color: #ef4444;
  }

  .kind.agent-kind {
    color: #c4b5fd;
  }

  .kind {
    font-size: 9px;
    font-weight: 700;
    color: var(--warn);
    letter-spacing: 0.05em;
  }

  strong {
    font-size: 12px;
  }

  .detail {
    font-size: 10px;
    color: var(--text-muted);
  }

  .tst-remaining {
    font-style: normal;
    color: #fca5a5;
    font-weight: 600;
  }

  .empty {
    font-size: 11px;
    color: var(--text-muted);
    padding: 8px;
  }

  @media (max-width: 768px) {
    .attention-rail {
      width: 100%;
      max-height: min(42vh, 320px);
      border-right: none;
      border-bottom: 1px solid var(--glass-border);
    }

    .attention-rail.collapsed {
      width: 100%;
      flex-direction: row;
      flex-wrap: wrap;
      justify-content: flex-start;
      align-items: center;
      gap: 6px;
      padding: 6px 8px;
      max-height: none;
    }

    .attention-rail.collapsed .expand-all {
      margin-bottom: 0;
    }

    .bubble {
      width: 44px;
      min-height: 36px;
    }
  }
</style>
