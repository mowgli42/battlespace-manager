import { describe, expect, it } from "vitest";
import { formatBandRange, interactionsForBand, ITU_BANDS } from "./rfBands.js";

describe("rfBands", () => {
  it("defines nine ITU bands", () => {
    expect(ITU_BANDS).toHaveLength(9);
    expect(ITU_BANDS.map((b) => b.label)).toEqual(["VLF", "LF", "MF", "HF", "VHF", "UHF", "SHF", "EHF", "THF"]);
  });

  it("formats HF range in MHz", () => {
    expect(formatBandRange(3, 30)).toBe("3–30 MHz");
  });

  it("filters interactions by band", () => {
    const list = [
      { interaction_id: "a", band_id: "uhf" },
      { interaction_id: "b", band_id: "shf" },
    ];
    expect(interactionsForBand(list, "uhf")).toHaveLength(1);
  });
});
