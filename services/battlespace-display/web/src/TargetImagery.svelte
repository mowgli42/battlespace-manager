<script>
  import { hasFix, snapshotTiles, seedHue } from "./lib/staticTiles.js";

  let { target = {}, task = null } = $props();

  let tab = $state("location");
  let sensor = $state("EO");

  let lat = $derived(Number(target.latitude) || 0);
  let lon = $derived(Number(target.longitude) || 0);
  let fix = $derived(hasFix(lat, lon));
  let tiles = $derived(snapshotTiles(lat, lon, 8));
  let hue = $derived(seedHue(target.target_id || target.task_id || task?.task_id));
  let title = $derived(target.target_name || target.target_id || task?.task_id || "Target");
</script>

<div class="imagery">
  <div class="img-tabs" role="tablist" aria-label="Task imagery">
    <button type="button" class:active={tab === "location"} onclick={() => (tab = "location")}>Location</button>
    <button type="button" class:active={tab === "imagery"} onclick={() => (tab = "imagery")}>Imagery</button>
  </div>

  {#if tab === "location"}
    <div class="frame location-frame" aria-label="Static location snapshot">
      {#if fix}
        <div class="tile-grid">
          {#each tiles as t (`${t.dx},${t.dy}`)}
            <img src={t.url} alt="" />
          {/each}
        </div>
        <div class="crosshair" aria-hidden="true"></div>
        <div class="fix-label">
          {lat.toFixed(3)}°, {lon.toFixed(3)}° · frozen
        </div>
      {:else}
        <svg viewBox="0 0 320 180" class="fallback-svg" role="img" aria-label="No geolocation">
          <rect width="320" height="180" fill="#08142b" />
          <text x="160" y="88" text-anchor="middle" fill="#8899aa" font-size="12">No geolocation for this task</text>
          <text x="160" y="108" text-anchor="middle" fill="#c8e6ff" font-size="11">{title}</text>
        </svg>
      {/if}
    </div>
  {:else}
    <div class="sensor-chips" role="tablist" aria-label="Sensor band">
      {#each ["EO", "IR", "SAR"] as band (band)}
        <button type="button" class:active={sensor === band} onclick={() => (sensor = band)}>{band}</button>
      {/each}
    </div>
    <div class="frame sensor-frame" style="--hue:{hue}" data-band={sensor}>
      <svg viewBox="0 0 320 180" class="sensor-svg" role="img" aria-label="{sensor} frame for {title}">
        <defs>
          <linearGradient id="g-{hue}" x1="0" x2="1">
            <stop offset="0%" stop-color="hsl({hue} 40% 12%)" />
            <stop offset="100%" stop-color="hsl({(hue + 40) % 360} 35% 8%)" />
          </linearGradient>
        </defs>
        <rect width="320" height="180" fill="url(#g-{hue})" />
        {#each [30, 70, 110, 150] as y (y)}
          <line x1="0" y1={y} x2="320" y2={y} stroke="hsla({hue},70%,70%,0.12)" stroke-width="1" />
        {/each}
        <circle cx="160" cy="90" r="28" fill="none" stroke="hsl({hue} 80% 65%)" stroke-width="1.5" />
        <circle cx="160" cy="90" r="3" fill="hsl({hue} 90% 70%)" />
        <text x="12" y="18" fill="hsl({hue} 70% 75%)" font-size="10" font-family="ui-monospace, monospace">{sensor} // {title}</text>
        <text x="12" y="168" fill="#8899aa" font-size="9" font-family="ui-monospace, monospace">
          {task?.task_id || target.task_id || "no-task"} · static frame
        </text>
      </svg>
    </div>
  {/if}
</div>

<style>
  .imagery {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 0;
    flex: 1;
  }
  .img-tabs,
  .sensor-chips {
    display: flex;
    gap: 6px;
  }
  .img-tabs button,
  .sensor-chips button {
    padding: 4px 10px;
    border-radius: 4px;
    border: 1px solid var(--glass-border);
    background: rgba(255, 255, 255, 0.04);
    color: var(--text-muted);
    font-size: 10px;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .img-tabs button.active,
  .sensor-chips button.active {
    border-color: var(--accent);
    color: var(--accent);
    background: rgba(0, 212, 255, 0.12);
  }
  .frame {
    position: relative;
    flex: 1;
    min-height: 200px;
    border-radius: 8px;
    border: 1px solid var(--glass-border);
    background: #08142b;
    overflow: hidden;
  }
  .tile-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    grid-template-rows: 1fr 1fr 1fr;
    width: 100%;
    height: 100%;
    min-height: 220px;
  }
  .tile-grid img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    filter: saturate(0.7);
  }
  .crosshair {
    position: absolute;
    inset: 50%;
    width: 18px;
    height: 18px;
    margin: -9px 0 0 -9px;
    border: 2px solid #ff7a45;
    border-radius: 50%;
    box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.6);
    pointer-events: none;
  }
  .fix-label {
    position: absolute;
    left: 8px;
    bottom: 8px;
    font-size: 10px;
    font-family: ui-monospace, monospace;
    color: #c8e6ff;
    background: rgba(0, 0, 0, 0.55);
    padding: 3px 6px;
    border-radius: 4px;
  }
  .fallback-svg,
  .sensor-svg {
    width: 100%;
    height: 100%;
    min-height: 200px;
    display: block;
  }
</style>
