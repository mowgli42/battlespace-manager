import { describe, expect, it } from "vitest";
import { hasFix, latLonToTile, seedHue } from "./staticTiles.js";

describe("staticTiles", () => {
  it("rejects missing fixes", () => {
    expect(hasFix(0, 0)).toBe(false);
    expect(hasFix(29.5, 47.7)).toBe(true);
  });

  it("maps a gulf coord to a tile", () => {
    const t = latLonToTile(29.5, 47.7, 8);
    expect(t.z).toBe(8);
    expect(t.x).toBeGreaterThan(0);
    expect(t.y).toBeGreaterThan(0);
  });

  it("seeds a stable hue per id", () => {
    expect(seedHue("tgt-1")).toBe(seedHue("tgt-1"));
    expect(seedHue("tgt-1")).not.toBe(seedHue("tgt-2"));
  });
});
