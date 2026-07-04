<script>
  import {
    buildConnectorModels,
    connectorHighlightState,
  } from "./lib/overlapConnectors.js";

  let {
    overlapBands = [],
    jamOnly = true,
    selectedAsset = null,
    gridWrapper = null,
  } = $props();

  let connectors = $state([]);
  let hoveredKey = $state(null);
  let svgSize = $state({ width: 0, height: 0 });

  function measureAssets() {
    if (!gridWrapper) {
      connectors = [];
      return;
    }
    const gridRect = gridWrapper.getBoundingClientRect();
    svgSize = { width: gridRect.width, height: gridRect.height };
    if (gridRect.width < 10 || gridRect.height < 10) return;

    const assetRects = new Map();
    for (const el of gridWrapper.querySelectorAll("[data-column][data-asset-id]")) {
      const col = el.getAttribute("data-column");
      const id = el.getAttribute("data-asset-id");
      if (col && id) assetRects.set(`${col}:${id}`, el.getBoundingClientRect());
    }

    connectors = buildConnectorModels(overlapBands, gridRect, assetRects, { jamOnly });
  }

  $effect(() => {
    overlapBands;
    jamOnly;
    selectedAsset;
    gridWrapper;
    queueMicrotask(measureAssets);
  });

  $effect(() => {
    if (!gridWrapper) return;
    const ro = new ResizeObserver(() => measureAssets());
    ro.observe(gridWrapper);
    return () => ro.disconnect();
  });

  function pathOpacity(model) {
    const state = connectorHighlightState(model, selectedAsset, hoveredKey);
    if (state === "active") return 0.95;
    if (state === "dim") return 0.12;
    return 0.55;
  }

  function pathWidth(model) {
    const state = connectorHighlightState(model, selectedAsset, hoveredKey);
    return state === "active" ? 2.5 : 1.5;
  }
</script>

{#if connectors.length > 0 && svgSize.width > 0}
  <svg
    class="overlap-connectors"
    width={svgSize.width}
    height={svgSize.height}
    aria-hidden="true"
  >
    {#each connectors as model (model.key)}
      <path
        d={model.path}
        role="button"
        tabindex="-1"
        class="connector-path {model.strokeClass}"
        stroke={model.strokeColor}
        stroke-width={pathWidth(model)}
        stroke-opacity={pathOpacity(model)}
        fill="none"
        onmouseenter={() => (hoveredKey = model.key)}
        onmouseleave={() => (hoveredKey = null)}
      >
        <title>{model.conflictType} · {model.frequencyMhz} MHz</title>
      </path>
    {/each}
  </svg>
{/if}
