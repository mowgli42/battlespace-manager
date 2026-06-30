import { describe, it, expect } from "vitest";
import { filterTracks, trackAffiliation, isMoving } from "./trackFilters.js";

describe("trackFilters", () => {
  const tracks = [
    {
      track_id: "a1",
      ground_speed_kts: 400,
      tags: ["Commercial", "Non-Threat"],
      threat_level: "Low",
      squawk: "1200",
      entity_type: "aircraft",
    },
    {
      track_id: "a2",
      ground_speed_kts: 10,
      tags: ["Alert"],
      threat_level: "High",
      squawk: "7700",
      entity_type: "aircraft",
    },
  ];

  it("derives affiliation", () => {
    expect(trackAffiliation(tracks[0])).toBe("friendly");
    expect(trackAffiliation(tracks[1])).toBe("hostile");
  });

  it("filters by affiliation", () => {
    const hostile = filterTracks(tracks, { affiliation: "hostile", kinematic: "all", entityType: "all", taggedOnly: false });
    expect(hostile).toHaveLength(1);
    expect(hostile[0].track_id).toBe("a2");
  });

  it("filters moving vs static", () => {
    const moving = filterTracks(tracks, { affiliation: "all", kinematic: "moving", entityType: "all", taggedOnly: false });
    expect(moving).toHaveLength(1);
    expect(isMoving(tracks[0])).toBe(true);
    expect(isMoving(tracks[1])).toBe(false);
  });
});
