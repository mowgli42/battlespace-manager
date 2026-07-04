import { describe, expect, it } from "vitest";
import { anyLiveService, formatScopes, statusLabel } from "./omsAiServices.js";

describe("omsAiServices", () => {
  it("formats scope labels", () => {
    expect(formatScopes(["targets", "tasks"])).toBe("Targets · Tasks");
  });

  it("detects live services", () => {
    expect(anyLiveService([{ status: "offline" }, { status: "live" }])).toBe(true);
    expect(anyLiveService([{ status: "offline" }])).toBe(false);
  });

  it("labels status", () => {
    expect(statusLabel("live")).toBe("Live");
    expect(statusLabel("offline")).toBe("Offline");
  });
});
