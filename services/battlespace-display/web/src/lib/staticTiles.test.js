import { describe, expect, it } from "vitest";
import { SUITE_DARK_TILES } from "./basemap.js";
import { hasFix, latLonToTile, seedHue, snapshotTiles, tileUrl } from "./staticTiles.js";

describe("staticTiles", () => {
  it("renders the suite dark tile endpoint", () => {
    const url = tileUrl(8, 161, 107);
    expect(url).toMatch(/^https:\/\/[abcd]\.basemaps\.cartocdn\.com\/dark_all\/8\/161\/107@2x\.png$/);
    expect(url).not.toContain("{");
    expect(tileUrl(8, 161, 107, { retina: false })).toMatch(/\/8\/161\/107\.png$/);
  });

  it("keeps snapshots within the suite zoom cap", () => {
    const tiles = snapshotTiles(29.5, 47.7, 18);
    expect(tiles).toHaveLength(9);
    for (const t of tiles) expect(t.url).toContain(`/dark_all/${SUITE_DARK_TILES.maxZoom}/`);
  });

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
