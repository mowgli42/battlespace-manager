<script>
  import { bandOccupancyClass, formatBandRange } from "./lib/rfBands.js";
  import { conflictTypeLabel } from "./lib/rfFormat.js";
  import { formatFreq } from "./lib/spectrumColumns.js";

  let {
    bandSummary = { bands: [], interactions: [] },
    selectedBandId = null,
    selectedInteractionId = null,
    onSelectBand = () => {},
    onSelectInteraction = () => {},
  } = $props();

  const bands = $derived(bandSummary.bands || []);
  const interactions = $derived(bandSummary.interactions || []);

  function bandInteractions(bandId) {
    return interactions.filter((i) => i.band_id === bandId);
  }

  function bandClass(band) {
    const classes = ["band-card", bandOccupancyClass(band)];
    if (selectedBandId === band.band_id) classes.push("selected");
    return classes.join(" ");
  }
</script>

<section class="band-overview" aria-label="ITU nine-band spectrum summary">
  <header class="band-overview-head">
    <h2>ITU spectrum bands</h2>
    <p class="hint">Nine radio-frequency groupings · select a band or interaction to drill down</p>
  </header>

  <div class="band-grid" role="list">
    {#each bands as band (band.band_id)}
      <button
        type="button"
        class={bandClass(band)}
        role="listitem"
        onclick={() => onSelectBand(band.band_id)}
        title="{band.name} · {formatBandRange(band.freq_range_mhz[0], band.freq_range_mhz[1])}"
      >
        <div class="band-top">
          <span class="band-label">{band.label}</span>
          <span class="band-number">#{band.number}</span>
        </div>
        <p class="band-name">{band.name}</p>
        <p class="band-range">{formatBandRange(band.freq_range_mhz[0], band.freq_range_mhz[1])}</p>
        <div class="band-meter" aria-hidden="true">
          <span
            class="band-fill"
            style="width: {Math.min(100, (band.occupant_count || 0) * 18)}%"
          ></span>
        </div>
        <div class="band-stats">
          <span>{band.occupant_count || 0} devices</span>
          {#if band.interaction_count}
            <span class="warn">{band.interaction_count} interactions</span>
          {/if}
        </div>
        {#if band.use_cases}
          <p class="band-use">{band.use_cases}</p>
        {/if}
      </button>
    {/each}
  </div>

  {#if selectedBandId}
    {@const band = bands.find((b) => b.band_id === selectedBandId)}
    {@const bandIx = bandInteractions(selectedBandId)}
    <div class="band-interactions">
      <h3>{band?.label} interactions</h3>
      {#if bandIx.length === 0}
        <p class="empty">No cross-device interactions in this band.</p>
      {:else}
        <ul>
          {#each bandIx as ix (ix.interaction_id)}
            <li>
              <button
                type="button"
                class:selected={selectedInteractionId === ix.interaction_id}
                onclick={() => onSelectInteraction(ix.interaction_id)}
              >
                <span class="ix-freq">{formatFreq(ix.frequency_mhz)}</span>
                <span class="ix-cols">{ix.columns?.join(" ↔ ")}</span>
                <span class="ix-type">{conflictTypeLabel(ix.conflict_type)}</span>
              </button>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}
</section>

<style>
  .band-overview {
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--border);
    background: linear-gradient(180deg, rgba(17, 26, 46, 0.95), rgba(11, 18, 32, 0.6));
  }
  .band-overview-head h2 {
    margin: 0;
    font-size: 0.72rem;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .hint {
    margin: 0.25rem 0 0.75rem;
    font-size: 0.72rem;
    color: var(--muted);
  }
  .band-grid {
    display: grid;
    grid-template-columns: repeat(9, minmax(0, 1fr));
    gap: 0.45rem;
  }
  @media (max-width: 1100px) {
    .band-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }
  .band-card {
    text-align: left;
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.5rem 0.55rem;
    background: rgba(8, 14, 28, 0.75);
    color: var(--text);
    cursor: pointer;
    min-height: 7.5rem;
    transition: border-color 0.15s, box-shadow 0.15s;
  }
  .band-card:hover {
    border-color: var(--accent);
  }
  .band-card.selected {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.35);
  }
  .band-card.empty {
    opacity: 0.55;
  }
  .band-card.active .band-fill {
    background: linear-gradient(90deg, #0ea5e9, #38bdf8);
  }
  .band-card.contested .band-fill {
    background: linear-gradient(90deg, #a78bfa, #f59e0b);
  }
  .band-card.jam .band-fill {
    background: linear-gradient(90deg, #f59e0b, #f87171);
  }
  .band-top {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 0.15rem;
  }
  .band-label {
    font-size: 0.95rem;
    font-weight: 700;
    letter-spacing: 0.04em;
  }
  .band-number {
    font-size: 0.62rem;
    color: var(--muted);
  }
  .band-name,
  .band-range,
  .band-use {
    margin: 0;
    font-size: 0.62rem;
    color: var(--muted);
    line-height: 1.3;
  }
  .band-range {
    margin: 0.2rem 0 0.35rem;
    font-family: ui-monospace, monospace;
    color: #94a3b8;
  }
  .band-meter {
    height: 4px;
    border-radius: 999px;
    background: rgba(36, 48, 73, 0.9);
    overflow: hidden;
    margin-bottom: 0.35rem;
  }
  .band-fill {
    display: block;
    height: 100%;
    border-radius: inherit;
    min-width: 2px;
  }
  .band-stats {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    font-size: 0.62rem;
    color: var(--text);
  }
  .band-stats .warn {
    color: var(--jam);
  }
  .band-use {
    margin-top: 0.25rem;
  }
  .band-interactions {
    margin-top: 0.85rem;
    padding-top: 0.65rem;
    border-top: 1px dashed var(--border);
  }
  .band-interactions h3 {
    margin: 0 0 0.5rem;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
  }
  .band-interactions ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }
  .band-interactions button {
    border: 1px solid var(--border);
    background: rgba(15, 23, 42, 0.8);
    color: var(--text);
    border-radius: 6px;
    padding: 0.35rem 0.55rem;
    font-size: 0.68rem;
    cursor: pointer;
    display: flex;
    gap: 0.45rem;
    align-items: center;
  }
  .band-interactions button.selected {
    border-color: var(--accent);
    background: rgba(14, 116, 144, 0.25);
  }
  .ix-freq {
    font-family: ui-monospace, monospace;
    color: var(--accent);
  }
  .ix-type {
    color: var(--jam);
  }
  .empty {
    margin: 0;
    font-size: 0.72rem;
    color: var(--muted);
  }
</style>
