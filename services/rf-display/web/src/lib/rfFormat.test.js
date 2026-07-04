import { describe, expect, it } from "vitest";
import { bandLabel, conflictTypeLabel } from "./rfFormat.js";

describe("bandLabel", () => {
  it("classifies HF and Ka", () => {
    expect(bandLabel(7.35)).toBe("HF");
    expect(bandLabel(14250)).toBe("Ku-band");
    expect(bandLabel(30000)).toBe("Ka+");
  });
});

describe("conflictTypeLabel", () => {
  it("maps jam_comm", () => {
    expect(conflictTypeLabel("jam_comm")).toBe("Jam ↔ Comms");
  });
});
