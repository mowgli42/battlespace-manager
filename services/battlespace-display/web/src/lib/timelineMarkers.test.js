import { describe, expect, it } from "vitest";
import { markerColor, markerGlyph, markerLabel } from "./timelineMarkers.js";

describe("timelineMarkers", () => {
  it("uses debrief glyphs", () => {
    expect(markerGlyph("diamond")).toBe("◆");
    expect(markerGlyph("caret")).toBe("▼");
    expect(markerGlyph("flag")).toBe("⚑");
    expect(markerGlyph("circle")).toBe("●");
  });

  it("labels marker kinds", () => {
    expect(markerLabel("caret")).toBe("strike");
    expect(markerLabel("diamond")).toBe("collect / ISR");
  });

  it("colors strike vs collect", () => {
    expect(markerColor("caret")).not.toBe(markerColor("diamond"));
  });
});
