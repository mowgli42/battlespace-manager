/** D3-backed frequency scales for the four-column spectrum view. */

import { scaleLinear, scaleLog } from "d3-scale";

export const SCALE_MODES = ["linear", "log"];

export function normalizeFreqRange(freqRange) {
  const [rawMin, rawMax] = freqRange || [0, 15000];
  const min = Number.isFinite(rawMin) ? rawMin : 0;
  const max = Number.isFinite(rawMax) ? rawMax : 15000;
  if (max <= min) return [min, min + 100];
  return [min, max];
}

export function createFreqScale(mode, freqRange) {
  const [min, max] = normalizeFreqRange(freqRange);
  if (mode === "log") {
    const logMin = Math.max(min, 1);
    const logMax = Math.max(max, logMin * 1.05);
    return scaleLog().domain([logMin, logMax]).range([0, 100]).clamp(true);
  }
  return scaleLinear().domain([min, max]).range([0, 100]).clamp(true);
}

export function freqTicks(scale, count = 8) {
  const ticks = scale.ticks(count);
  return ticks.map((value) => ({ value, pct: scale(value) }));
}

export function assetBarStyle(asset, scaleOrRange, mode = "linear") {
  const scale = typeof scaleOrRange === "function" ? scaleOrRange : createFreqScale(mode, scaleOrRange);
  const low = asset.freq_low_mhz ?? asset.frequency_mhz - (asset.bandwidth_mhz || 1) / 2;
  const high = asset.freq_high_mhz ?? asset.frequency_mhz + (asset.bandwidth_mhz || 1) / 2;
  const bottom = scale(low);
  const top = scale(high);
  const height = Math.max(3, top - bottom);
  return {
    bottom: `${Math.max(0, Math.min(97, bottom))}%`,
    height: `${Math.min(40, height)}%`,
  };
}

export function overlapMidpointPct(asset, scale) {
  const low = asset.freq_low_mhz ?? asset.frequency_mhz - (asset.bandwidth_mhz || 1) / 2;
  const high = asset.freq_high_mhz ?? asset.frequency_mhz + (asset.bandwidth_mhz || 1) / 2;
  return scale((low + high) / 2);
}
