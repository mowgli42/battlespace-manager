<script>
  let { picture = {}, onPhaseClick = () => {} } = $props();

  let mt = $derived(picture.mission_thread || {});
  let phases = $derived(mt.f2t2ea_phases || ["Find", "Fix", "Track", "Target", "Engage", "Assess"]);
  let counts = $derived(mt.phase_counts || {});
  let dominant = $derived(mt.dominant_phase || "Find");
  let events = $derived(mt.timeline_events || []);

  const PHASE_COLORS = {
    Find: "#3b82f6",
    Fix: "#eab308",
    Track: "#22c55e",
    Target: "#f97316",
    Engage: "#ef4444",
    Assess: "#a855f7",
  };
</script>

<div class="mission-thread" role="navigation" aria-label="F2T2EA mission thread">
  <div class="phase-rail">
    {#each phases as ph (ph)}
      <button
        type="button"
        class="phase-node"
        class:dominant={ph === dominant}
        style="--ph-color: {PHASE_COLORS[ph]}"
        title="{ph}: {counts[ph] ?? 0} targets"
        onclick={() => onPhaseClick(ph)}
      >
        <span class="ph-name">{ph}</span>
        <span class="ph-count">{counts[ph] ?? 0}</span>
      </button>
    {/each}
  </div>
  <div class="timeline-scroll" aria-label="Scenario timeline">
    {#each events as ev, i (`${ev.sim_offset}-${ev.event_type}-${i}`)}
      <span class="tl-ev tl-{ev.status}" title="{ev.narrative}">
        <em>T+{ev.sim_offset}</em> {ev.event_type || "EVENT"}
      </span>
    {/each}
  </div>
</div>

<style>
  .mission-thread {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 16px;
    background: rgba(8, 14, 28, 0.95);
    border-bottom: 1px solid var(--glass-border);
  }
  .phase-rail {
    display: flex;
    gap: 6px;
  }
  .phase-node {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    padding: 6px 4px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-muted);
    cursor: pointer;
    font-size: 10px;
  }
  .phase-node:hover {
    border-color: var(--ph-color);
    color: var(--text-primary);
  }
  .phase-node.dominant {
    border-color: var(--ph-color);
    background: color-mix(in srgb, var(--ph-color) 18%, transparent);
    color: var(--ph-color);
    font-weight: 600;
  }
  .ph-name {
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .ph-count {
    font-family: ui-monospace, monospace;
    font-size: 11px;
  }
  .timeline-scroll {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 2px;
    font-size: 10px;
  }
  .tl-ev {
    flex-shrink: 0;
    padding: 4px 8px;
    border-radius: 4px;
    background: rgba(255, 255, 255, 0.06);
    color: var(--text-muted);
    max-width: 180px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tl-ev em {
    font-style: normal;
    color: var(--accent);
    margin-right: 4px;
  }
  .tl-past {
    opacity: 0.55;
  }
  .tl-imminent {
    border: 1px solid var(--warn);
    color: var(--warn);
  }
  .tl-future {
    border: 1px dashed rgba(255, 255, 255, 0.15);
  }
</style>
