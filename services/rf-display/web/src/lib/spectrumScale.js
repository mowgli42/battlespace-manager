/** D3-backed frequency scales for the four-column spectrum view. */

import { scaleLinear, scaleLog, scaleSymlog } from "d3-scale";

export const SCALE_MODES = ["linear", "log", "symlog"];
export const SYMLOG_CONSTANT = 1;

export function normalizeFreqRange(freqRange) {
  const [rawMin, rawMax] = freqRange || [0, 15000];
  const min = Number.isFinite(rawMin) ? rawMin : 0;
  const max = Number.isFinite(rawMax) ? rawMax : 15000;
  if (max <= min) return [min, min + 100];
  return [min, max];
}

export function effectiveDomain(fullRange, brushDomain) {
  if (!brushDomain) return normalizeFreqRange(fullRange);
  const [bMin, bMax] = normalizeFreqRange(brushDomain);
  const [fMin, fMax] = normalizeFreqRange(fullRange);
  return [Math.max(bMin, fMin), Math.min(bMax, fMax)];
}

export function createFreqScale(mode, freqRange, brushDomain = null) {
  const [min, max] = effectiveDomain(freqRange, brushDomain);
  if (mode === "symlog") {
    const sMin = Math.max(min, 0.001);
    const sMax = Math.max(max, sMin * 1.05);
    return scaleSymlog()
      .constant(SYMLOG_CONSTANT)
      .domain([sMin, sMax])
      .range([0, 100])
      .clamp(true);
  }
  if (mode === "log") {
    const logMin = Math.max(min, 1);
    const logMax = Math.max(max, logMin * 1.05);
    return scaleLog().domain([logMin, logMax]).range([0, 100]).clamp(true);
  }
  return scaleLinear().domain([min, max]).range([0, 100]).clamp(true);
}

/** Pixel-range scale for brush interaction (y=0 top, y=height bottom in SVG). */
export function createBrushScale(mode, freqRange, heightPx, brushDomain = null) {
  const [min, max] = effectiveDomain(freqRange, brushDomain);
  const pctScale = createFreqScale(mode, [min, max]);
  return (freq) => (heightPx * (100 - pctScale(freq))) / 100;
}

export function invertBrushScale(mode, freqRange, heightPx, yPx, brushDomain = null) {
  const [min, max] = effectiveDomain(freqRange, brushDomain);
  const domain = normalizeFreqRange([min, max]);

  let scale;
  if (mode === "symlog") {
    scale = scaleSymlog().constant(SYMLOG_CONSTANT).domain([Math.max(domain[0], 0.001), domain[1]]);
  } else if (mode === "log") {
    scale = scaleLog().domain([Math.max(domain[0], 1), domain[1]]);
  } else {
    scale = scaleLinear().domain(domain);
  }
  scale.range([heightPx, 0]);
  return scale.invert(yPx);
}

export function brushSelectionToDomain(mode, fullRange, heightPx, selection, currentBrushDomain = null) {
  if (!selection) return null;
  const [y0, y1] = selection;
  const f0 = invertBrushScale(mode, fullRange, heightPx, y0, currentBrushDomain);
  const f1 = invertBrushScale(mode, fullRange, heightPx, y1, currentBrushDomain);
  return [Math.min(f0, f1), Math.max(f0, f1)];
}

export function freqTicks(scale, count = 8) {
  const ticks = scale.ticks(count);
  return ticks.map((value) => ({ value, pct: scale(value) }));
}

export function bandStyle(low, high, scale) {
  const bottom = scale(low);
  const top = scale(high);
  const height = Math.max(1.5, top - bottom);
  return {
    bottom: `${Math.max(0, Math.min(97, bottom))}%`,
    height: `${Math.min(100, height)}%`,
  };
}

export function assetBarStyle(asset, scaleOrRange, mode = "linear") {
  const scale =
    typeof scaleOrRange === "function" ? scaleOrRange : createFreqScale(mode, scaleOrRange);
  const low = asset.freq_low_mhz ?? asset.frequency_mhz - (asset.bandwidth_mhz || 1) / 2;
  const high = asset.freq_high_mhz ?? asset.frequency_mhz + (asset.bandwidth_mhz || 1) / 2;
  return bandStyle(low, high, scale);
}

export function overlapMidpointPct(asset, scale) {
  const low = asset.freq_low_mhz ?? asset.frequency_mhz - (asset.bandwidth_mhz || 1) / 2;
  const high = asset.freq_high_mhz ?? asset.frequency_mhz + (asset.bandwidth_mhz || 1) / 2;
  return scale((low + high) / 2);
}
