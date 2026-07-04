import { describe, expect, it } from "vitest";
import {
  assetBarStyle,
  brushSelectionToDomain,
  createFreqScale,
  effectiveDomain,
  freqTicks,
  normalizeFreqRange,
} from "./spectrumScale.js";

describe("spectrumScale", () => {
  it("normalizes invalid ranges", () => {
    expect(normalizeFreqRange([100, 100])).toEqual([100, 200]);
  });

  it("creates linear, log, and symlog scales", () => {
    const linear = createFreqScale("linear", [0, 1000]);
    const log = createFreqScale("log", [1, 10000]);
    const symlog = createFreqScale("symlog", [0.01, 15000]);
    expect(linear(0)).toBe(0);
    expect(linear(1000)).toBe(100);
    expect(log(1)).toBeCloseTo(0, 1);
    expect(symlog(7.35)).toBeGreaterThan(0);
    expect(symlog(1575)).toBeGreaterThan(symlog(7.35));
  });

  it("symlog separates HF and GPS better than log at low end", () => {
    const log = createFreqScale("log", [1, 15000]);
    const symlog = createFreqScale("symlog", [0.1, 15000]);
    const hfGpsGapLog = log(1575) - log(7.35);
    const hfGpsGapSym = symlog(1575) - symlog(7.35);
    expect(symlog(7.35)).toBeGreaterThan(log(7.35));
    expect(hfGpsGapSym).toBeLessThan(hfGpsGapLog);
  });

  it("applies brush domain zoom", () => {
    const full = createFreqScale("linear", [0, 1000]);
    const zoomed = createFreqScale("linear", [0, 1000], [200, 400]);
    expect(zoomed(200)).toBe(0);
    expect(zoomed(400)).toBe(100);
    expect(zoomed(300)).toBeGreaterThan(full(300));
  });

  it("effectiveDomain clamps brush to full range", () => {
    expect(effectiveDomain([0, 1000], [100, 500])).toEqual([100, 500]);
    expect(effectiveDomain([0, 1000], [-50, 2000])).toEqual([0, 1000]);
  });

  it("brush selection converts to frequency domain", () => {
    const domain = brushSelectionToDomain("linear", [0, 1000], 200, [50, 150], null);
    expect(domain[0]).toBeCloseTo(250, 0);
    expect(domain[1]).toBeCloseTo(750, 0);
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
    const ticks = freqTicks(createFreqScale("symlog", [0.1, 10000]), 5);
    expect(ticks.length).toBeGreaterThan(2);
    expect(ticks[0]).toHaveProperty("pct");
  });
});
