<script>
  import FusionPanel from "./FusionPanel.svelte";
  import PlatformContextPanel from "./PlatformContextPanel.svelte";

  let { picture = {}, selectedEntityId = $bindable(null), onSelectEntity = () => {} } = $props();

  let feeds = $derived(picture.feed_status || []);
</script>

<div class="sources-panel">
  <section class="feed-strip" aria-label="Sensor feed status">
    <h2>Sensor feeds</h2>
    <div class="feed-cards">
      {#each feeds as f (f.feed_id)}
        <div class="feed-card" class:active={f.active}>
          <span class="feed-id">{f.feed_id}</span>
          <span class="feed-type">{f.type}</span>
          <span class="feed-stat">{f.active ? "LIVE" : "OFF"} · {f.tracks_last_tick} tracks/tick</span>
          <span class="feed-role">{f.role}</span>
        </div>
      {/each}
    </div>
  </section>
  <section class="fusion-section">
    <FusionPanel {picture} bind:selectedEntityId {onSelectEntity} />
  </section>
  <section class="platform-section">
    <PlatformContextPanel {picture} bind:selectedEntityId {onSelectEntity} />
  </section>
</div>

<style>
  .sources-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }
  .feed-strip {
    flex-shrink: 0;
    padding: 12px 16px;
    border-bottom: 1px solid var(--glass-border);
    background: rgba(8, 14, 28, 0.95);
  }
  .feed-strip h2 {
    margin: 0 0 10px;
    font-size: 12px;
    text-transform: uppercase;
    color: var(--accent);
    letter-spacing: 0.05em;
  }
  .feed-cards {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .feed-card {
    flex: 1 1 160px;
    max-width: 220px;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--glass-border);
    background: rgba(0, 0, 0, 0.25);
    font-size: 10px;
    display: flex;
    flex-direction: column;
    gap: 2px;
    opacity: 0.65;
  }
  .feed-card.active {
    opacity: 1;
    border-color: var(--ok);
    box-shadow: 0 0 0 1px rgba(74, 222, 128, 0.2);
  }
  .feed-id {
    font-weight: 700;
    color: var(--text-primary);
  }
  .feed-type {
    color: var(--accent);
  }
  .feed-stat {
    font-family: ui-monospace, monospace;
    color: var(--ok);
  }
  .feed-role {
    color: var(--text-muted);
    font-size: 9px;
  }
  .fusion-section {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }
  .platform-section {
    flex: 0 0 220px;
    min-height: 180px;
    max-height: 280px;
    display: flex;
    flex-direction: column;
    border-top: 1px solid var(--glass-border);
  }
</style>
