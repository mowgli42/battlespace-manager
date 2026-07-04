<script>
  import { buildJrflCorridors, corridorRestrictionClass } from "./lib/jrflCorridors.js";

  let { entries = [], scale = null } = $props();

  const corridors = $derived(scale ? buildJrflCorridors(entries, scale) : []);
</script>

{#if corridors.length > 0}
  <div class="jrfl-corridor-layer" aria-hidden="true">
    {#each corridors as corridor (corridor.id)}
      <div
        class="jrfl-corridor {corridorRestrictionClass(corridor.restriction)}"
        style={corridor.style}
        title="{corridor.label} · {corridor.frequency_mhz} MHz · {corridor.restriction}"
      ></div>
    {/each}
  </div>
{/if}
