import { describe, expect, it } from "vitest";
import { getSidc, sidcCacheKey } from "./sidc.js";

describe("getSidc", () => {
  it("maps hostile air to SHAP base", () => {
    expect(getSidc({ affiliation: "OPFOR", domain: "AIR" })).toBe("SHAP-----------");
  });

  it("maps coalition air to SFAP base", () => {
    expect(getSidc({ affiliation: "COALITION", domain: "AIR" })).toBe("SFAP-----------");
  });

  it("maps hostile surface SAM to equipment modifier", () => {
    expect(getSidc({ affiliation: "OPFOR", domain: "SURFACE", platform_type: "SA-6" })).toBe("SHGPE-----------");
  });

  it("maps unknown affiliation to U", () => {
    expect(getSidc({ affiliation: "MYSTERY", domain: "GROUND" })).toBe("SUGP-----------");
  });

  it("builds stable cache keys", () => {
    expect(sidcCacheKey({ affiliation: "opfor", domain: "air", platform_type: "MiG-29" })).toBe(
      "OPFOR|AIR|MIG-29",
    );
  });
});
