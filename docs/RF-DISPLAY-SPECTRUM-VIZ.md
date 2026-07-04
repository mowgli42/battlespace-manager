# RF Display — Spectrum Visualization Research

Design reference for phase 3 D3 enhancements to the four-column EMSO deconfliction view.

## Operator requirement

Show **four spectrum columns** (Radar Threats · Jammers · Comm · Support) on a **shared frequency axis**, with visible **cross-column overlap** especially where friendly jamming collides with comm or support RF (GPS, friendly radars, datalinks).

## Patterns evaluated

### 1. Horizontal band chart (D3 rects on shared axis)

**Reference:** [chrisfarnham/frequency-chart-library](https://gist.github.com/chrisfarnham/5f396b506efaf64118516b286929a41d)

- `d3.scaleLinear` maps start/end frequency to `rect` width on one axis.
- Multiple emitters use vertical `yOffset` to avoid label collision.
- **Fit:** Excellent for single-row “waterfall” or strip charts; less natural for four parallel role columns.
- **Adopted as:** Per-column vertical bands (CSS + shared scale), not a single horizontal strip.

### 2. Log-scaled electromagnetic spectrum

**Reference:** [Cameron Rye — Electromagnetic Spectrum Explorer](https://rye.dev/blog/electromagnetic-spectrum-explorer/)

- HF through Ka spans **orders of magnitude** (MHz–GHz); linear scale compresses HF/VHF into a sliver.
- `d3.scaleLog` (or symlog below 1 MHz) is standard for spectrum allocators and EMS tools.
- **Fit:** Essential toggle for our Gulf War slice (7 MHz HF nets → 14 GHz SATCOM).
- **Adopted as:** Header toggle **Linear / Log** driving `d3.scaleLinear` vs `d3.scaleLog` for axis ticks and asset placement.

### 3. Parallel coordinates (cross-column links)

**References:**
- [syntagmatic/parallel-coordinates](http://syntagmatic.github.io/parallel-coordinates/)
- [D3 graph gallery — custom parallel coords](https://d3-graph-gallery.com/graph/parallel_custom.html)
- [Stack Overflow — shaded bands between parallel axes](https://stackoverflow.com/questions/27771893/d3-parallel-coordinates-drawing-two-lines-to-show-a-range-and-shading-the-regi)

- Each column is a vertical axis; **paths** connect the same logical entity or overlapping band across axes.
- Hover dims unrelated paths (`opacity` transition) — good deconfliction UX.
- Frequency **ranges** can be drawn as shaded corridors between two Y positions on adjacent axes.
- **Fit:** Closest match to “show where overlaps occur between jammers and comm/support.”
- **Adopted as:** SVG **bezier connector layer** over the four columns, keyed on `overlap_bands` / `jam_*` conflicts, with hover highlight.

### 4. Parallel sets / chord (rejected for now)

**Reference:** [Jason Davies — Parallel Sets](https://www.jasondavies.com/parallel-sets/)

- Better for categorical flow volume than precise frequency placement.
- **Fit:** Poor — we need MHz fidelity, not aggregate counts.

## Chosen architecture (phase 3)

```
┌────────┬──────────────────────────────────────────────────────────┐
│  Freq  │  Threat  │  Jammers  │   Comm   │  Support  │ Legend  │
│  axis  │  column  │  column   │  column  │  column   │         │
│ (d3)   │          │           │          │           │         │
├────────┼──────────┴───────────┴──────────┴───────────┴─────────┤
│        │  SVG connector layer (d3.path / cubic bezier)           │
│        │  jam_comm / jam_support = red, jam_radar = amber        │
└────────┴──────────────────────────────────────────────────────────┘
```

| Layer | Technology | Responsibility |
|-------|------------|----------------|
| Frequency scale | `d3-scale` linear + log | Shared Y mapping for axis ticks and asset bars |
| Asset bars | Svelte + CSS `%` bottom/height | Column-local labels, click, JAMMED flags |
| Connectors | SVG overlay + `ResizeObserver` | Bezier links between measured asset centers |
| Interaction | Svelte state | Scale toggle, asset select, connector hover dim |

## Implementation notes

- **Log domain floor:** clamp minimum to 1 MHz so HF nets remain visible without `scaleSymlog` complexity in v1.
- **Connector filter:** default **Jam overlaps only**; optional “All overlaps” for band collisions.
- **Performance:** typical picture has &lt;30 assets and &lt;20 connectors — DOM measurement on SSE update is acceptable; debounce on resize.

## Beads (phase 3)

| ID | Task |
|----|------|
| `battlespace-manager-q93` | Epic — D3 spectrum viz |
| `battlespace-manager-nfj` | 3.1 This research doc |
| `battlespace-manager-ovw` | 3.2 Log/linear scale toggle |
| `battlespace-manager-dv2` | 3.3 SVG overlap connectors |
| `battlespace-manager-c8b` | 3.4 Walkthrough screenshots |

## Future (phase 4+)

- `d3.scaleSymlog` for sub-MHz HF guard nets alongside GPS L1.
- Shaded **frequency corridors** (parallel-coords band shading) for JRFL protected regions.
- Brush/zoom on frequency axis for dense EA scenarios.
