import { describe, expect, it } from "vitest";
import { affiliationToForce, entityToTrack } from "./trackFromEntity.js";

describe("entityToTrack", () => {
  it("maps OPFOR air entity to hostile track", () => {
    const track = entityToTrack(
      {
        entity_id: "E-OPFOR-1",
        latitude: 29.5,
        longitude: 47.2,
        affiliation: "OPFOR",
        domain: "AIR",
        platform_type: "MiG-29",
        confidence: 0.92,
      },
      15,
    );
    expect(track.id).toBe("E-OPFOR-1");
    expect(track.force).toBe("hostile");
    expect(track.lat).toBe(29.5);
    expect(track.metadata?.platform_type).toBe("MiG-29");
    expect(track.timestamp).toBe(15);
  });

  it("maps coalition platform to friendly", () => {
    expect(affiliationToForce("COALITION")).toBe("friendly");
    const track = entityToTrack({
      entity_id: "COAL-1",
      latitude: 25.9,
      longitude: 55.4,
      affiliation: "COALITION",
      domain: "AIR",
    });
    expect(track.force).toBe("friendly");
  });

  it("rejects invalid entity payload", () => {
    expect(() => entityToTrack({ entity_id: "x" })).toThrow();
  });
});
