<script>
  import { normalizeDrilldown } from "./lib/rfBands.js";
  import { conflictTypeLabel } from "./lib/rfFormat.js";
  import { COLUMN_META, formatFreq } from "./lib/spectrumColumns.js";

  let { interaction = null, onClose = () => {} } = $props();

  const drilldown = $derived(interaction ? normalizeDrilldown(interaction) : null);
  const devices = $derived(drilldown?.devices || []);

  function columnColor(column) {
    return COLUMN_META[column]?.color || "#64748b";
  }
</script>

{#if drilldown}
  <section class="interaction-drilldown" aria-label="Interaction drill-down">
    <header>
      <div>
        <h2>Interaction drill-down</h2>
        <p>
          {formatFreq(drilldown.frequency_mhz)}
          · {drilldown.columns?.join(" ↔ ")}
          · <span class="ctype">{conflictTypeLabel(drilldown.conflict_type)}</span>
        </p>
      </div>
      <button type="button" class="close" onclick={onClose}>Clear</button>
    </header>

    <div class="channel-stage">
      <div class="spectrum-plot-bg" aria-hidden="true">
        {#each Array(24) as _, i}
          <span class="plot-line" style="left: {(i / 23) * 100}%"></span>
        {/each}
      </div>

      <div class="channel-axis">
        <span>{formatFreq(drilldown.freq_low_mhz)}</span>
        <span class="axis-title">Operating devices · relative power</span>
        <span>{formatFreq(drilldown.freq_high_mhz)}</span>
      </div>

      <div class="device-lanes">
        {#each devices as device (device.asset_id + device.column)}
          <div class="device-lane">
            <div class="lane-meta">
              <span class="lane-dot" style="background: {columnColor(device.column)}"></span>
              <strong>{device.label}</strong>
              <span class="lane-col">{device.column}</span>
              <span class="lane-freq">{formatFreq(device.frequency_mhz)}</span>
              {#if device.jamming_active}
                <span class="lane-flag">TX</span>
              {/if}
              {#if device.jammed}
                <span class="lane-flag jammed">JAMMED</span>
              {/if}
            </div>
            <div class="channel-track">
              <div
                class="channel-bar"
                style="
                  left: {device.channel_left_pct}%;
                  width: {Math.max(device.channel_width_pct, 4)}%;
                  height: {Math.max(device.power_pct, 12)}%;
                  --bar-color: {columnColor(device.column)};
                "
                title="{device.label} · power {device.power_pct?.toFixed?.(0) ?? device.power_level}%"
              >
                <span class="power-label">{device.power_pct?.toFixed?.(0) ?? Math.round((device.power_level || 0) * 100)}%</span>
              </div>
            </div>
          </div>
        {/each}
      </div>

      <p class="plot-note">RF spectrogram placeholder — channel width ∝ overlap; bar height ∝ relative transmit power.</p>
    </div>
  </section>
{/if}

<style>
  .interaction-drilldown {
    margin: 0 1rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: rgba(10, 16, 30, 0.92);
    overflow: hidden;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.65rem 0.85rem;
    border-bottom: 1px solid var(--border);
    background: rgba(17, 26, 46, 0.85);
  }
  h2 {
    margin: 0;
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--muted);
  }
  header p {
    margin: 0.2rem 0 0;
    font-size: 0.78rem;
    color: var(--text);
  }
  .ctype {
    color: var(--jam);
  }
  .close {
    border: 1px solid var(--border);
    background: transparent;
    color: var(--muted);
    border-radius: 6px;
    padding: 0.25rem 0.55rem;
    font-size: 0.68rem;
    cursor: pointer;
  }
  .channel-stage {
    position: relative;
    padding: 0.75rem 0.85rem 0.65rem;
  }
  .spectrum-plot-bg {
    position: absolute;
    inset: 2.5rem 0.85rem 2.2rem;
    border-radius: 6px;
    background: repeating-linear-gradient(
      180deg,
      rgba(15, 23, 42, 0.35) 0,
      rgba(15, 23, 42, 0.35) 12px,
      rgba(8, 12, 24, 0.2) 12px,
      rgba(8, 12, 24, 0.2) 24px
    );
    pointer-events: none;
    opacity: 0.55;
  }
  .plot-line {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 1px;
    background: rgba(56, 189, 248, 0.08);
  }
  .channel-axis {
    position: relative;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.65rem;
    color: var(--muted);
    font-family: ui-monospace, monospace;
    margin-bottom: 0.55rem;
  }
  .axis-title {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-family: inherit;
  }
  .device-lanes {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }
  .device-lane {
    display: grid;
    gap: 0.25rem;
  }
  .lane-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    align-items: center;
    font-size: 0.72rem;
  }
  .lane-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
  }
  .lane-col {
    color: var(--muted);
    font-size: 0.65rem;
  }
  .lane-freq {
    font-family: ui-monospace, monospace;
    color: var(--accent);
    font-size: 0.65rem;
  }
  .lane-flag {
    font-size: 0.58rem;
    padding: 0.05rem 0.3rem;
    border-radius: 4px;
    background: rgba(245, 158, 11, 0.2);
    color: var(--jam);
  }
  .lane-flag.jammed {
    background: rgba(248, 113, 113, 0.2);
    color: var(--hostile);
  }
  .channel-track {
    position: relative;
    height: 3.25rem;
    border: 1px solid rgba(36, 48, 73, 0.9);
    border-radius: 6px;
    background: rgba(4, 8, 18, 0.65);
    overflow: hidden;
  }
  .channel-bar {
    position: absolute;
    bottom: 0;
    min-width: 2rem;
    border-radius: 4px 4px 0 0;
    background: linear-gradient(180deg, color-mix(in srgb, var(--bar-color) 85%, white), var(--bar-color));
    border: 1px solid color-mix(in srgb, var(--bar-color) 70%, white);
    display: flex;
    align-items: flex-end;
    justify-content: center;
    padding-bottom: 0.15rem;
    transition: height 0.2s ease;
  }
  .power-label {
    font-size: 0.58rem;
    color: rgba(255, 255, 255, 0.9);
    font-weight: 600;
  }
  .plot-note {
    margin: 0.55rem 0 0;
    font-size: 0.62rem;
    color: var(--muted);
  }
</style>
