import { describe, expect, it } from "vitest";
import {
  buildConnectorModels,
  connectorEndpoints,
  connectorPath,
  filterConnectorBands,
} from "./overlapConnectors.js";

describe("overlapConnectors", () => {
  it("filters jam-only bands", () => {
    const bands = [
      { conflict_type: "jam_comm", asset_ids: ["a", "b"], columns: ["jammers", "comm"] },
      { conflict_type: "band_overlap", asset_ids: ["c", "d"], columns: ["comm", "support"] },
    ];
    expect(filterConnectorBands(bands, { jamOnly: true })).toHaveLength(1);
    expect(filterConnectorBands(bands, { jamOnly: false })).toHaveLength(2);
  });

  it("builds cubic bezier path", () => {
    expect(connectorPath(10, 20, 90, 40)).toMatch(/^M 10 20 C/);
  });

  it("resolves endpoints left-to-right", () => {
    const grid = { left: 0, top: 0, right: 400, bottom: 200, width: 400, height: 200 };
    const rects = new Map([
      ["jammers:j1", { left: 100, right: 180, top: 50, height: 20 }],
      ["comm:c1", { left: 220, right: 300, top: 80, height: 24 }],
    ]);
    const pts = connectorEndpoints(grid, rects, "jammers", "j1", "comm", "c1");
    expect(pts?.x1).toBe(180);
    expect(pts?.x2).toBe(220);
  });

  it("builds connector models from overlap bands", () => {
    const grid = { left: 0, top: 0, right: 400, bottom: 200, width: 400, height: 200 };
    const rects = new Map([
      ["jammers:j1", { left: 100, right: 180, top: 50, height: 20 }],
      ["support:GPS_L1", { left: 300, right: 380, top: 60, height: 18 }],
    ]);
    const models = buildConnectorModels(
      [
        {
          conflict_type: "jam_support",
          asset_ids: ["j1", "GPS_L1"],
          columns: ["jammers", "support"],
          frequency_mhz: 1575,
        },
      ],
      grid,
      rects,
    );
    expect(models).toHaveLength(1);
    expect(models[0].strokeClass).toBe("overlap-jam-critical");
  });
});
