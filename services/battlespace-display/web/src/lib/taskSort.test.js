import { describe, expect, it } from "vitest";
import { sortTaskRows } from "./taskSort.js";

describe("sortTaskRows", () => {
  it("puts TST rows before non-TST", () => {
    const rows = [
      { task_id: "a", is_time_sensitive: false, priority: 1 },
      { task_id: "b", is_time_sensitive: true, priority: 9 },
    ];
    expect(sortTaskRows(rows).map((r) => r.task_id)).toEqual(["b", "a"]);
  });

  it("sorts by priority when TST flag matches", () => {
    const rows = [
      { task_id: "low", is_time_sensitive: true, priority: 5 },
      { task_id: "high", is_time_sensitive: true, priority: 1 },
    ];
    expect(sortTaskRows(rows).map((r) => r.task_id)).toEqual(["high", "low"]);
  });

  it("sorts by assigned_at_sim when TST and priority match", () => {
    const rows = [
      { task_id: "old", is_time_sensitive: false, priority: 3, assigned_at_sim: 1 },
      { task_id: "new", is_time_sensitive: false, priority: 3, assigned_at_sim: 10 },
    ];
    expect(sortTaskRows(rows).map((r) => r.task_id)).toEqual(["new", "old"]);
  });
});
