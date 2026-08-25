<script>
  import { markerColor, markerGlyph, markerLabel } from "./lib/timelineMarkers.js";

  let {
    picture = {},
    onSelectEntity = () => {},
    onOpenDecisions = () => {},
  } = $props();

  const ZOOM_STEPS = [10, 30, 60, 180, 360, 720];
  const PAST_FRACTION = 0.25;

  let roleFilter = $state("all");
  let selectedEventId = $state(null);
  let zoomMin = $state(60);

  let tv = $derived(picture.timeline_view || {});
  let sim = $derived(tv.sim_minutes ?? picture.sim_minutes ?? 0);
  let zoomSpans = $derived(
    Array.isArray(tv.zoom_spans_minutes) && tv.zoom_spans_minutes.length ? tv.zoom_spans_minutes : ZOOM_STEPS
  );
  let pastFrac = $derived(typeof tv.past_fraction === "number" ? tv.past_fraction : PAST_FRACTION);
  let axisStart = $derived(Math.max(0, sim - zoomMin * pastFrac));
  let axisMax = $derived(sim + zoomMin * (1 - pastFrac));
  let tracks = $derived(tv.tracks || []);

  let roles = $derived.by(() => {
    const set = new Set();
    for (const tr of tracks) {
      if (tr.operational_role) set.add(tr.operational_role);
    }
    return [...set].sort();
  });

  let visibleTracks = $derived.by(() => {
    if (roleFilter === "all") return tracks;
    return tracks.filter((tr) => (tr.operational_role || "") === roleFilter || tr.aircraft_id === "MISSION");
  });

  let selectedEvent = $derived.by(() => {
    for (const tr of tracks) {
      for (const ev of tr.events || []) {
        if (ev.id === selectedEventId) return { ...ev, track: tr };
      }
    }
    return null;
  });

  let visibleEvents = $derived.by(() => {
    const row = [];
    for (const tr of visibleTracks) {
      for (const ev of tr.events || []) {
        const t = Number(ev.t_min);
        if (t < axisStart - 0.05 || t > axisMax + 0.05) continue;
        row.push({ ...ev, track: tr });
      }
    }
    row.sort((a, b) => (a.t_min || 0) - (b.t_min || 0));
    return row;
  });

  let milestones = $derived(visibleEvents.filter((ev) => Number(ev.t_min) >= sim - 0.05));

  function fmtSim(m) {
    const v = Number(m) || 0;
    const mins = Math.floor(v);
    const secs = Math.round((v % 1) * 60);
    return `T+${mins}:${String(secs).padStart(2, "0")}`;
  }

  function pct(t) {
    const span = Math.max(1, axisMax - axisStart);
    return Math.min(100, Math.max(0, ((Number(t) - axisStart) / span) * 100));
  }

  function ticks() {
    const span = axisMax - axisStart;
    const step = span > 240 ? 60 : span > 90 ? 30 : span > 40 ? 15 : span > 20 ? 5 : 2;
    const out = [axisStart];
    const first = Math.ceil((axisStart + 0.01) / step) * step;
    for (let t = first; t < axisMax - 0.05; t += step) {
      if (Math.abs(t - sim) < step * 0.35) continue;
      out.push(t);
    }
    out.push(sim);
    out.push(axisMax);
    return out;
  }

  function tickLabel(t) {
    const d = Number(t) - sim;
    if (Math.abs(d) < 0.4) return "NOW";
    const sign = d < 0 ? "−" : "+";
    return sign + spanLabel(Math.abs(d));
  }

  function spanLabel(m) {
    const n = Math.round(Number(m));
    if (n < 60) return `${n}m`;
    const h = Math.floor(n / 60);
    const rem = n % 60;
    return rem ? `${h}h${rem}m` : `${h}h`;
  }

  function setZoom(span) {
    const steps = zoomSpans;
    const nearest = steps.reduce((best, s) => (Math.abs(s - span) < Math.abs(best - span) ? s : best), steps[0]);
    zoomMin = nearest;
  }

  function zoomBy(dir) {
    const steps = zoomSpans;
    const idx = steps.findIndex((s) => s === zoomMin);
    const next = idx < 0 ? 60 : steps[Math.max(0, Math.min(steps.length - 1, idx + dir))];
    zoomMin = next;
  }

  function onMarker(ev, _tr) {
    selectedEventId = ev.id;
    if (ev.entity_id) onSelectEntity(ev.entity_id);
    if (ev.kind === "strike" || ev.kind === "collect" || ev.kind === "task") onOpenDecisions();
  }

  function eventsInWindow(tr) {
    return (tr.events || []).filter((ev) => {
      const t = Number(ev.t_min);
      return t >= axisStart - 0.05 && t <= axisMax + 0.05;
    });
  }
</script>

<div class="timeline-panel">
  <header class="tl-header">
    <div>
      <h2>Aligned timeline</h2>
      <p class="tl-sub">
        {tv.note || "One lane per aircraft · shared mission time"}
        {#if tracks.length} · {tracks.length} lanes{/if}
      </p>
    </div>
    <div class="tl-controls">
      <div class="tl-zoom" role="group" aria-label="Timeline zoom">
        <button type="button" class="zoom-btn" onclick={() => zoomBy(-1)} disabled={zoomMin === zoomSpans[0]} title="Zoom in">−</button>
        {#each zoomSpans as span (span)}
          <button type="button" class="zoom-btn" class:active={zoomMin === span} onclick={() => setZoom(span)}>
            {spanLabel(span)}
          </button>
        {/each}
        <button type="button" class="zoom-btn" onclick={() => zoomBy(1)} disabled={zoomMin === zoomSpans[zoomSpans.length - 1]} title="Zoom out">+</button>
      </div>
      <div class="tl-now" aria-label="Current simulation time">
        <span class="tl-now-lbl">NOW · {spanLabel(zoomMin * pastFrac)} back / {spanLabel(zoomMin * (1 - pastFrac))} ahead</span>
        <span class="tl-now-val">{fmtSim(sim)}</span>
      </div>
    </div>
  </header>

  <div class="tl-legend" aria-label="Event markers">
    {#each ["flag", "diamond", "caret", "circle"] as mk (mk)}
      <span class="leg" style="color:{markerColor(mk)}">
        <span class="leg-g">{markerGlyph(mk)}</span>
        {markerLabel(mk)}
      </span>
    {/each}
  </div>

  {#if roles.length}
    <div class="tl-filters" role="tablist" aria-label="Aircraft role filter">
      <button type="button" class:active={roleFilter === "all"} onclick={() => (roleFilter = "all")}>All</button>
      {#each roles as role (role)}
        <button type="button" class:active={roleFilter === role} onclick={() => (roleFilter = role)}>{role}</button>
      {/each}
    </div>
  {/if}

  {#if !visibleTracks.length}
    <p class="tl-empty">No aircraft tracks yet — waiting for OMS platform status on the bus.</p>
  {:else}
    <div class="tl-axis" aria-hidden="true">
      <span class="tl-axis-gutter"></span>
      <div class="tl-axis-scale">
        {#each ticks() as tick, i (`${tick}-${i}`)}
          <span class="tl-tick" class:now={Math.abs(tick - sim) < 0.4} style="left:{pct(tick)}%">{tickLabel(tick)}</span>
        {/each}
      </div>
    </div>

    <div class="tl-tracks" role="list" aria-label="Aircraft timelines">
      {#each visibleTracks as tr (tr.aircraft_id)}
        <div class="tl-row" role="listitem">
          <button
            type="button"
            class="tl-label"
            title="{tr.aircraft_id} · {tr.route_name || '—'}"
            onclick={() => tr.aircraft_id !== "MISSION" && onSelectEntity(tr.aircraft_id)}
          >
            <span class="tl-callsign">{tr.label || tr.aircraft_id}</span>
            <span class="tl-meta">{tr.aircraft_type || "—"}{#if tr.operational_role} · {tr.operational_role}{/if}</span>
          </button>
          <div class="tl-track">
            <div class="tl-past" style="width:{pastFrac * 100}%" title="Elapsed"></div>
            {#each tr.segments || [] as seg, i (`${tr.aircraft_id}-seg-${i}`)}
              <div
                class="tl-seg"
                style="left:{pct(seg.t0)}%;width:{Math.max(0.4, pct(Math.min(seg.t1, sim)) - pct(seg.t0))}%"
                title="{seg.from_id} → {seg.to_id}"
              ></div>
            {/each}
            {#each eventsInWindow(tr) as ev (ev.id)}
              <button
                type="button"
                class="tl-mark"
                class:active={selectedEventId === ev.id}
                style="left:{pct(ev.t_min)}%;color:{markerColor(ev.marker)}"
                title="{fmtSim(ev.t_min)} · {ev.label}{ev.detail ? ' · ' + ev.detail : ''}"
                onclick={() => onMarker(ev, tr)}
              >
                {markerGlyph(ev.marker)}
              </button>
            {/each}
            <div class="tl-playhead" style="left:{pct(sim)}%" title="NOW {fmtSim(sim)}"></div>
          </div>
        </div>
      {/each}
    </div>
  {/if}

  {#if selectedEvent}
    <div class="tl-detail" role="status">
      <span class="leg-g" style="color:{markerColor(selectedEvent.marker)}">{markerGlyph(selectedEvent.marker)}</span>
      <strong>{fmtSim(selectedEvent.t_min)}</strong>
      <span>{selectedEvent.label}</span>
      {#if selectedEvent.detail}<span class="muted">{selectedEvent.detail}</span>{/if}
      {#if selectedEvent.track}<span class="muted">{selectedEvent.track.label}</span>{/if}
    </div>
  {/if}

  <div class="milestones" aria-label="Upcoming timeline events">
    {#each milestones as ev (ev.id)}
      <button
        type="button"
        class="milestone"
        class:active={selectedEventId === ev.id}
        onclick={() => onMarker(ev, ev.track)}
      >
        <span class="ms-mark" style="color:{markerColor(ev.marker)}">{markerGlyph(ev.marker)}</span>
        <span class="ms-time">{fmtSim(ev.t_min)}</span>
        <span class="ms-who">{ev.track?.label || ""}</span>
        <span class="ms-title">{ev.label}</span>
      </button>
    {:else}
      <p class="tl-empty">No upcoming events in this zoom window.</p>
    {/each}
  </div>
</div>

<style>
  .timeline-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    padding: 14px 18px;
    background: rgba(6, 12, 24, 0.98);
    overflow: hidden;
  }
  .tl-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    margin-bottom: 8px;
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
    font-size: 11px;
    color: var(--text-muted);
  }
  .tl-controls {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
  }
  .tl-zoom {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 4px;
  }
  .zoom-btn {
    min-width: 2rem;
    padding: 4px 7px;
    border-radius: 4px;
    border: 1px solid var(--glass-border);
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-muted);
    font-size: 10px;
    font-family: ui-monospace, monospace;
    cursor: pointer;
  }
  .zoom-btn.active {
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(0, 212, 255, 0.12);
  }
  .zoom-btn:disabled {
    opacity: 0.35;
    cursor: default;
  }
  .tl-now {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    padding: 6px 10px;
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
    font-size: 16px;
    font-weight: 700;
    color: var(--accent);
  }
  .tl-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    font-size: 11px;
    color: var(--text-muted);
    margin-bottom: 8px;
    flex-shrink: 0;
  }
  .leg {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
  .leg-g {
    font-size: 13px;
    line-height: 1;
  }
  .tl-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 10px;
    flex-shrink: 0;
  }
  .tl-filters button {
    padding: 4px 10px;
    border-radius: 6px;
    border: 1px solid var(--glass-border);
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-muted);
    font-size: 10px;
    cursor: pointer;
  }
  .tl-filters button.active {
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(0, 212, 255, 0.12);
  }
  .tl-axis {
    display: grid;
    grid-template-columns: 9.5rem 1fr;
    gap: 10px;
    margin-bottom: 4px;
    flex-shrink: 0;
  }
  .tl-axis-scale {
    position: relative;
    height: 18px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }
  .tl-tick {
    position: absolute;
    bottom: 2px;
    transform: translateX(-50%);
    font-size: 9px;
    font-family: ui-monospace, monospace;
    color: var(--text-muted);
  }
  .tl-tick.now {
    color: var(--accent);
    font-weight: 700;
  }
  .tl-tracks {
    flex: 0 1 auto;
    max-height: 52%;
    overflow-y: auto;
    padding-right: 4px;
  }
  .tl-row {
    display: grid;
    grid-template-columns: 9.5rem 1fr;
    gap: 10px;
    align-items: center;
    margin-bottom: 6px;
  }
  .tl-label {
    text-align: left;
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    padding: 0;
    min-width: 0;
  }
  .tl-callsign {
    display: block;
    font-size: 12px;
    font-weight: 700;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tl-meta {
    display: block;
    font-size: 10px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .tl-track {
    position: relative;
    height: 28px;
    border-radius: 4px;
    border: 1px solid var(--glass-border);
    background: rgba(0, 0, 0, 0.35);
    overflow: hidden;
  }
  .tl-past {
    position: absolute;
    inset: 0 auto 0 0;
    background: rgba(255, 255, 255, 0.04);
    border-right: 1px dashed rgba(255, 255, 255, 0.12);
    pointer-events: none;
  }
  .tl-seg {
    position: absolute;
    top: 8px;
    height: 12px;
    background: rgba(0, 212, 255, 0.28);
    border-radius: 2px;
  }
  .tl-mark {
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    background: none;
    border: none;
    cursor: pointer;
    font-size: 14px;
    line-height: 1;
    padding: 2px;
    z-index: 2;
  }
  .tl-mark:hover {
    transform: translate(-50%, -50%) scale(1.25);
  }
  .tl-mark.active {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
    border-radius: 2px;
    z-index: 3;
  }
  .tl-playhead {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    background: #fff;
    opacity: 0.75;
    transform: translateX(-50%);
    pointer-events: none;
    z-index: 1;
    box-shadow: 0 0 8px var(--accent);
  }
  .tl-detail {
    flex-shrink: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin: 10px 0 6px;
    padding: 8px 10px;
    border-radius: 6px;
    border: 1px solid var(--glass-border);
    background: rgba(0, 212, 255, 0.06);
    font-size: 12px;
  }
  .tl-detail strong {
    font-family: ui-monospace, monospace;
    color: var(--accent);
  }
  .muted {
    color: var(--text-muted);
  }
  .milestones {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-top: 6px;
  }
  .milestone {
    display: grid;
    grid-template-columns: 1.2rem 4.5rem 5rem 1fr;
    gap: 8px;
    align-items: center;
    text-align: left;
    width: 100%;
    padding: 6px 8px;
    border-radius: 6px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(255, 255, 255, 0.03);
    color: inherit;
    cursor: pointer;
    font-size: 11px;
  }
  .milestone:hover,
  .milestone.active {
    border-color: var(--accent);
    background: rgba(0, 212, 255, 0.08);
  }
  .ms-mark {
    font-size: 13px;
    text-align: center;
  }
  .ms-time {
    font-family: ui-monospace, monospace;
    color: var(--accent);
  }
  .ms-who {
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .ms-title {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .tl-empty {
    color: var(--text-muted);
    font-size: 13px;
    padding: 24px;
    text-align: center;
  }
</style>
