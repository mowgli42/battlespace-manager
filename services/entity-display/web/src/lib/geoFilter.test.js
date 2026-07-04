import { describe, expect, it } from "vitest";
import { haversineNm, pointNearRoute } from "./geoFilter.js";
import { overlaySummaryText, routeTooltip } from "./detectionOverlay.js";

describe("geoFilter", () => {
  it("computes haversine distance", () => {
    expect(haversineNm(0, 0, 0, 1)).toBeGreaterThan(50);
  });

  it("detects point near route", () => {
    const route = [
      [28, 48],
      [29, 48.5],
    ];
    expect(pointNearRoute(28.5, 48.2, route, 15)).toBe(true);
    expect(pointNearRoute(28.5, 50, route, 1)).toBe(false);
  });
});

describe("detectionOverlay", () => {
  it("formats route tooltip", () => {
    const tip = routeTooltip({
      callsign: "RAVEN01",
      route_name: "SEAD-TRANSIT",
      pattern: "transit",
      buffer_nm: 8,
    });
    expect(tip).toContain("RAVEN01");
    expect(tip).toContain("8 nm");
  });

  it("formats overlay summary", () => {
    const text = overlaySummaryText({
      fog_zone_count: 2,
      route_corridor_count: 3,
      route_target_alert_count: 1,
    });
    expect(text).toContain("2 fog");
    expect(text).toContain("1 alerts");
  });
});
