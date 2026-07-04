import { describe, expect, it } from "vitest";
import { assetBarStyle, isJammed, overlapClass } from "./spectrumColumns.js";

describe("spectrumColumns", () => {
  it("marks jam comm overlaps as critical", () => {
    expect(overlapClass("jam_comm")).toBe("overlap-jam-critical");
    expect(overlapClass("jam_support")).toBe("overlap-jam-critical");
  });

  it("computes bar position from frequency bounds", () => {
    const style = assetBarStyle(
      { frequency_mhz: 1000, freq_low_mhz: 990, freq_high_mhz: 1010 },
      [0, 2000],
    );
    expect(parseFloat(style.bottom)).toBeCloseTo(49.5, 0);
    expect(parseFloat(style.height)).toBeGreaterThan(0);
  });

  it("detects jammed assets", () => {
    expect(isJammed({ jammed_by: [{ asset_id: "j1" }] })).toBe(true);
    expect(isJammed({ jammed_by: [] })).toBe(false);
  });
});
