<script>
  import { bandColor, bandForDistance, placeTasksOnRoute } from "./lib/routeImpact.js";

  let {
    routeName = "",
    threatEntityId = "",
    closestNm = null,
    severity = "",
    segments = [],
    cumulativeNm = [],
    waypoints = [],
    closestIndex = 0,
    selectedSegmentIndex = null,
    onboardTasks = [],
    nearbyTasks = [],
    axisMode = "distance",
    onSelectSegment = () => {},
    onRequestSupport = () => {},
    onAxisChange = () => {},
  } = $props();

  let totalNm = $derived(cumulativeNm.length ? cumulativeNm[cumulativeNm.length - 1] : 0);
  let closestPct = $derived.by(() => {
    if (!totalNm || !cumulativeNm.length) return 50;
    const base = cumulativeNm[closestIndex] ?? 0;
    const next = cumulativeNm[closestIndex + 1] ?? base;
    return ((base + next) / 2 / totalNm) * 100;
  });

  let onboard = $derived(placeTasksOnRoute(onboardTasks, routeName, waypoints, cumulativeNm));
  let nearby = $derived(placeTasksOnRoute(nearbyTasks, routeName, waypoints, cumulativeNm));

  const REQUESTS = [
    { id: "STRIKE", label: "Request Strike", band: "STRIKE" },
    { id: "EJ", label: "Request EJ", band: "EJ" },
    { id: "JAM", label: "Request Jam", band: "JAM" },
  ];
</script>

<section class="route-timeline" aria-label="Route segment timeline">
  <header>
    <div>
      <h2>Route timeline · {routeName || "—"}</h2>
      <p class="hint">
        {threatEntityId || "threat"} closest {closestNm != null ? `${Number(closestNm).toFixed(1)} nm` : "—"}
        {#if severity} · {severity}{/if}
        · select a segment for detail · support requests queue locally until bus publish lands
      </p>
    </div>
    <div class="axis-toggle" role="group" aria-label="Timeline axis">
      <button type="button" class:active={axisMode === "distance"} onclick={() => onAxisChange("distance")}>Distance</button>
      <button type="button" class:active={axisMode === "time"} onclick={() => onAxisChange("time")}>Time</button>
    </div>
  </header>

  <div class="tracks">
    <div class="track-label">Impact</div>
    <div class="track-line impact">
      {#each segments as seg (seg.index)}
        <button
          type="button"
          class="seg"
          class:selected={selectedSegmentIndex === seg.index}
          class:closest={seg.index === closestIndex}
          style="flex:{Math.max(seg.length_nm, 0.5)}; background:{seg.color}"
          title={`Seg ${seg.index + 1} · ${seg.closest_nm.toFixed(1)} nm · ${seg.band}`}
          onclick={() => onSelectSegment(seg)}
        ></button>
      {/each}
      <span class="threat-mark" style="left:{closestPct}%" title="Threat closest approach">▼</span>
    </div>

    <div class="track-label">Onboard</div>
    <div class="track-line tasks">
      <div class="rail"></div>
      {#each onboard as t (t.task_id)}
        <button
          type="button"
          class="task-mark onboard"
          style="left:{t.pct}%; border-color:{bandColor(bandForDistance(t.cost_nm))}"
          title={`${t.role} · ${t.task_id}`}
          onclick={() => onSelectSegment({ index: closestIndex, task: t })}
        >
          {t.role?.slice(0, 3) || "TSK"}
        </button>
      {/each}
    </div>

    <div class="track-label dim">Nearby</div>
    <div class="track-line tasks nearby">
      <div class="rail"></div>
      {#each nearby as t (t.task_id)}
        <span
          class="task-mark nearby-mark"
          style="left:{t.pct}%"
          title={`${t.role} · ${t.task_id} · ${t.route_name || ""}`}
        >{t.role?.slice(0, 1) || "·"}</span>
      {/each}
    </div>

    <div class="track-label"></div>
    <div class="axis">
      <span>0 {axisMode === "time" ? "min" : "nm"}</span>
      <span>{axisMode === "time" ? "~ETA" : `${totalNm.toFixed(0)} nm`}</span>
    </div>
  </div>

  <div class="actions">
    {#each REQUESTS as r (r.id)}
      <button
        type="button"
        class="req"
        style="--band:{bandColor(r.band)}"
        onclick={() => onRequestSupport(r.id)}
      >
        {r.label}
      </button>
    {/each}
    <span class="actions-hint">Publishes as local nomination stub (uci.task request path TBD)</span>
  </div>
</section>

<style>
  .route-timeline {
    flex-shrink: 0;
    border-top: 1px solid var(--glass-border, rgba(148, 163, 184, 0.25));
    background: rgba(6, 12, 24, 0.96);
    padding: 10px 14px 12px;
    max-height: 42%;
    overflow: auto;
  }
  header {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: flex-start;
    margin-bottom: 10px;
  }
  h2 {
    margin: 0 0 2px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent, #00d4ff);
  }
  .hint {
    margin: 0;
    font-size: 10px;
    color: var(--text-muted, #94a3b8);
    line-height: 1.35;
  }
  .axis-toggle {
    display: flex;
    gap: 4px;
  }
  .axis-toggle button {
    font-size: 10px;
    padding: 4px 8px;
    border-radius: 4px;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: transparent;
    color: #cbd5e1;
    cursor: pointer;
  }
  .axis-toggle button.active {
    border-color: var(--accent, #00d4ff);
    color: var(--accent, #00d4ff);
  }
  .tracks {
    display: grid;
    grid-template-columns: 64px 1fr;
    gap: 6px 10px;
    align-items: center;
  }
  .track-label {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #94a3b8;
  }
  .track-label.dim {
    opacity: 0.65;
  }
  .track-line {
    position: relative;
    min-height: 18px;
  }
  .track-line.impact {
    display: flex;
    height: 14px;
    border-radius: 4px;
    overflow: hidden;
    gap: 1px;
  }
  .seg {
    border: none;
    padding: 0;
    cursor: pointer;
    min-width: 4px;
    opacity: 0.85;
  }
  .seg:hover,
  .seg.selected {
    opacity: 1;
    outline: 1px solid #fff;
    z-index: 1;
  }
  .seg.closest {
    box-shadow: inset 0 0 0 1px #fff;
  }
  .threat-mark {
    position: absolute;
    top: -12px;
    transform: translateX(-50%);
    color: #ef4444;
    font-size: 10px;
    pointer-events: none;
  }
  .track-line.tasks {
    height: 28px;
  }
  .rail {
    position: absolute;
    left: 0;
    right: 0;
    top: 50%;
    height: 2px;
    background: rgba(148, 163, 184, 0.35);
    transform: translateY(-50%);
  }
  .track-line.nearby .rail {
    background: rgba(148, 163, 184, 0.18);
  }
  .task-mark {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    font-size: 9px;
    font-weight: 700;
    padding: 2px 5px;
    border-radius: 4px;
    border: 1px solid #f97316;
    background: rgba(15, 23, 42, 0.95);
    color: #e2e8f0;
    cursor: pointer;
    white-space: nowrap;
  }
  .task-mark.nearby-mark {
    border-color: rgba(148, 163, 184, 0.45);
    color: #94a3b8;
    background: rgba(15, 23, 42, 0.6);
    cursor: default;
  }
  .axis {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: #64748b;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-top: 10px;
  }
  .req {
    font-size: 11px;
    font-weight: 600;
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid var(--band);
    color: var(--band);
    background: transparent;
    cursor: pointer;
  }
  .req:hover {
    background: color-mix(in srgb, var(--band) 18%, transparent);
  }
  .actions-hint {
    font-size: 10px;
    color: #64748b;
  }
</style>
