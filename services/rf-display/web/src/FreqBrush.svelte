<script>
  import { brushY } from "d3-brush";
  import { select } from "d3-selection";
  import { brushSelectionToDomain } from "./lib/spectrumScale.js";

  let {
    gridWrapper = null,
    freqScaleMode = "symlog",
    fullRange = [0, 15000],
    brushDomain = null,
    brushResetToken = 0,
    onBrushDomain = () => {},
  } = $props();

  let brushHost = $state(null);
  let brushHeight = $state(0);
  let headerOffset = $state(0);

  function measure() {
    if (!gridWrapper) return;
    const header = gridWrapper.querySelector(".column-header");
    const canvas = gridWrapper.querySelector(".column-canvas");
    headerOffset = header?.offsetHeight ?? 0;
    brushHeight = canvas?.offsetHeight ?? 0;
  }

  function setupBrush() {
    if (!brushHost || brushHeight < 20) return;

    const brush = brushY()
      .extent([
        [0, 0],
        [32, brushHeight],
      ])
      .on("end", (event) => {
        if (!event.sourceEvent) return;
        const domain = brushSelectionToDomain(
          freqScaleMode,
          fullRange,
          brushHeight,
          event.selection,
          brushDomain,
        );
        onBrushDomain(domain);
      });

    const sel = select(brushHost);
    sel.selectAll("*").remove();
    sel.append("g").attr("class", "brush").call(brush);
  }

  $effect(() => {
    gridWrapper;
    measure();
  });

  $effect(() => {
    brushHost;
    freqScaleMode;
    fullRange;
    brushHeight;
    headerOffset;
    setupBrush();
  });

  $effect(() => {
    if (brushResetToken === 0 || !brushHost) return;
    select(brushHost).select(".brush").call(brushY().move, null);
  });

  $effect(() => {
    if (!gridWrapper) return;
    const ro = new ResizeObserver(() => measure());
    ro.observe(gridWrapper);
    return () => ro.disconnect();
  });
</script>

<div
  class="freq-brush-host"
  bind:this={brushHost}
  style="top: {headerOffset}px; height: {brushHeight}px"
  aria-label="Frequency brush — drag to zoom band"
></div>
