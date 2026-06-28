<script>
  let { items = [], selectedEntityId = null, onSelect = () => {} } = $props();

  let summary = $derived.by(() => {
    const counts = {};
    for (const item of items) {
      counts[item.kind] = (counts[item.kind] || 0) + 1;
    }
    const parts = [];
    if (counts.TST) parts.push(`${counts.TST} time-sensitive`);
    if (counts.POPUP) parts.push(`${counts.POPUP} pop-up`);
    if (counts.TARGET) parts.push(`${counts.TARGET} target`);
    if (counts.TASK) parts.push(`${counts.TASK} task`);
    if (counts.CUSTODY) parts.push(`${counts.CUSTODY} custody`);
    if (counts.AGENT) parts.push(`${counts.AGENT} advisor`);
    return parts.length ? parts.join(" · ") : "No urgent items — monitoring battlespace";
  });
</script>

<aside class="attention-rail" aria-label="Operator attention queue">
  <h2>Attention</h2>
  <p class="hint" aria-live="polite">{summary}</p>
  <ul>
    {#each items as item (item.id)}
      <li>
        <button
          type="button"
          class:selected={selectedEntityId === item.entity_id}
          class:urgent={item.urgency <= 1}
          class:tst={item.kind === "TST"}
          class:agent={item.kind === "AGENT"}
          onclick={() => onSelect(item)}
        >
          <span class="kind" class:agent-kind={item.kind === "AGENT"} class:tst-kind={item.kind === "TST"}>{item.kind}</span>
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
      <li class="empty">Queue clear — battlespace nominal</li>
    {/each}
  </ul>
</aside>

<style>
  .attention-rail {
    width: 240px;
    flex-shrink: 0;
    border-right: 1px solid var(--glass-border);
    background: rgba(6, 12, 24, 0.98);
    padding: 12px;
    overflow-y: auto;
    min-height: 0;
  }
  h2 {
    margin: 0 0 4px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent);
  }
  .hint {
    margin: 0 0 10px;
    font-size: 10px;
    color: var(--text-muted);
    line-height: 1.35;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
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
</style>
