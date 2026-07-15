import { describe, expect, it } from "vitest";
import {
  bandForDistance,
  buildImpactSegments,
  haversineNm,
  placeTasksOnRoute,
} from "./routeImpact.js";

describe("routeImpact", () => {
  it("bands match popup-tasker thresholds", () => {
    expect(bandForDistance(10)).toBe("STRIKE");
    expect(bandForDistance(50)).toBe("STRIKE");
    expect(bandForDistance(75)).toBe("EJ");
    expect(bandForDistance(140)).toBe("JAM");
    expect(bandForDistance(200)).toBe("OUT");
  });

  it("builds colored segments toward a threat", () => {
    const wps = [
      [29.0, 48.0],
      [29.1, 47.8],
      [29.2, 47.65],
      [29.3, 47.5],
    ];
    const impact = buildImpactSegments(wps, 29.25, 47.65);
    expect(impact.segments.length).toBe(3);
    expect(impact.closestNm).toBeLessThan(50);
    expect(impact.segments.some((s) => s.band === "STRIKE")).toBe(true);
  });

  it("haversine is symmetric and positive", () => {
    const d = haversineNm(29.0, 48.0, 30.0, 48.0);
    expect(d).toBeGreaterThan(50);
    expect(haversineNm(30.0, 48.0, 29.0, 48.0)).toBeCloseTo(d, 5);
  });

  it("places onboard tasks along cumulative distance", () => {
    const wps = [
      [29.0, 48.0],
      [29.1, 47.8],
      [29.2, 47.6],
    ];
    const impact = buildImpactSegments(wps, 29.15, 47.7);
    const placed = placeTasksOnRoute(
      [{ task_id: "T1", role: "STRIKE", route_name: "CAP-BOX", latitude: 29.15, longitude: 47.7 }],
      "CAP-BOX",
      impact.waypoints,
      impact.cumulativeNm
    );
    expect(placed).toHaveLength(1);
    expect(placed[0].pct).toBeGreaterThan(0);
    expect(placed[0].pct).toBeLessThanOrEqual(100);
  });
});
