import { describe, expect, it } from "vitest";
import { buildJrflCorridors, jrflCorridorBounds } from "./jrflCorridors.js";
import { createFreqScale } from "./spectrumScale.js";

describe("jrflCorridors", () => {
  it("computes corridor frequency bounds", () => {
    const b = jrflCorridorBounds({ frequency_mhz: 969, bandwidth_mhz: 3 });
    expect(b.low).toBeCloseTo(967.5);
    expect(b.high).toBeCloseTo(970.5);
  });

  it("builds positioned corridors with scale", () => {
    const scale = createFreqScale("linear", [0, 2000]);
    const rows = buildJrflCorridors(
      [{ id: "j1", frequency_mhz: 1000, bandwidth_mhz: 20, label: "Test", restriction: "NO_EA" }],
      scale,
    );
    expect(rows).toHaveLength(1);
    expect(rows[0].style.bottom).toBeDefined();
    expect(rows[0].style.height).toBeDefined();
  });
});
