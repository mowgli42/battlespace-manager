import { describe, expect, it, afterEach } from "vitest";
import { clearIconCache, createMilIcon, getOrCreateMilIcon } from "./milSymbol.js";

describe("milSymbol", () => {
  afterEach(() => clearIconCache());

  it("creates Leaflet icon with data URL", () => {
    const icon = createMilIcon({ affiliation: "OPFOR", domain: "AIR" });
    expect(icon.options.iconUrl).toMatch(/^data:image/);
  });

  it("reuses cached icons for same entity type", () => {
    const entity = { affiliation: "COALITION", domain: "AIR", platform_type: "F-16C" };
    const a = getOrCreateMilIcon(entity);
    const b = getOrCreateMilIcon(entity);
    expect(a).toBe(b);
  });
});
