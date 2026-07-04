import { describe, expect, it } from "vitest";
import {
  geoFilterMatches,
  haversineNm,
  pointInCircle,
  pointInPolygon,
  pointNearRoute,
} from "./geoFilter.js";

describe("geoFilter", () => {
  it("computes haversine distance", () => {
    expect(haversineNm(0, 0, 0, 1)).toBeGreaterThan(50);
  });

  it("detects point in circle", () => {
    expect(pointInCircle(28.5, 48.0, 28.5, 48.0, 10)).toBe(true);
    expect(pointInCircle(30, 48, 28.5, 48, 10)).toBe(false);
  });

  it("detects point in polygon", () => {
    const square = [
      [27, 48],
      [29, 48],
      [29, 49],
      [27, 49],
    ];
    expect(pointInPolygon(28, 48.5, square)).toBe(true);
    expect(pointInPolygon(26, 48.5, square)).toBe(false);
  });

  it("detects point near route", () => {
    const route = [
      [28, 48],
      [29, 48.5],
    ];
    expect(pointNearRoute(28.5, 48.2, route, 15)).toBe(true);
    expect(pointNearRoute(28.5, 50, route, 1)).toBe(false);
  });

  it("matches active geo filter object", () => {
    const filter = {
      type: "circle",
      active: true,
      geometry: { center_lat: 28.45, center_lon: 48.35, radius_nm: 20 },
    };
    expect(geoFilterMatches(28.45, 48.35, filter)).toBe(true);
    expect(geoFilterMatches(30, 48.35, filter)).toBe(false);
    expect(geoFilterMatches(30, 48.35, null)).toBe(true);
  });
});
