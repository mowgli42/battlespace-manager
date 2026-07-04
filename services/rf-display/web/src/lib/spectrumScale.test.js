import { describe, expect, it } from "vitest";
import { assetBarStyle, createFreqScale, freqTicks, normalizeFreqRange } from "./spectrumScale.js";

describe("spectrumScale", () => {
  it("normalizes invalid ranges", () => {
    expect(normalizeFreqRange([100, 100])).toEqual([100, 200]);
  });

  it("creates linear and log scales", () => {
    const linear = createFreqScale("linear", [0, 1000]);
    const log = createFreqScale("log", [1, 10000]);
    expect(linear(0)).toBe(0);
    expect(linear(1000)).toBe(100);
    expect(log(1)).toBeCloseTo(0, 1);
    expect(log(10000)).toBeCloseTo(100, 1);
  });

  it("log scale spreads HF vs GHz more than linear", () => {
    const range = [1, 15000];
    const linear = createFreqScale("linear", range);
    const log = createFreqScale("log", range);
    const linearSpan = linear(10000) - linear(10);
    const logSpan = log(10000) - log(10);
    expect(logSpan).toBeGreaterThan(linearSpan);
  });

  it("positions asset bars with scale", () => {
    const scale = createFreqScale("linear", [0, 2000]);
    const style = assetBarStyle(
      { frequency_mhz: 1000, freq_low_mhz: 990, freq_high_mhz: 1010 },
      scale,
    );
    expect(parseFloat(style.bottom)).toBeCloseTo(49.5, 0);
    expect(parseFloat(style.height)).toBeGreaterThan(0);
  });

  it("emits axis ticks", () => {
    const ticks = freqTicks(createFreqScale("log", [1, 10000]), 5);
    expect(ticks.length).toBeGreaterThan(2);
    expect(ticks[0]).toHaveProperty("pct");
  });
});
