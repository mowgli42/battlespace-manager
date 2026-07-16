import { describe, expect, it } from "vitest";
import {
  countByFilter,
  countBySliders,
  filterBySliders,
  filterTaskRows,
  isHighPriority,
  isTaskUnassigned,
  isTstTask,
  suggestAutoFilter,
  suggestSliderState,
} from "./taskFilters.js";

const rows = [
  {
    task_id: "a",
    priority: 1,
    is_time_sensitive: true,
    lifecycle_state: "NEW",
    assigned_platform_id: "",
  },
  {
    task_id: "b",
    priority: 2,
    is_time_sensitive: false,
    lifecycle_state: "ASSIGNMENT",
    assigned_platform_id: "",
  },
  {
    task_id: "c",
    priority: 1,
    is_time_sensitive: true,
    lifecycle_state: "ACCEPTED",
    assigned_platform_id: "P1",
  },
  {
    task_id: "d",
    priority: 3,
    is_time_sensitive: false,
    lifecycle_state: "NEW",
    assigned_platform_id: "",
  },
];

describe("taskFilters", () => {
  it("detects unassigned tasks", () => {
    expect(isTaskUnassigned(rows[0])).toBe(true);
    expect(isTaskUnassigned(rows[2])).toBe(false);
  });

  it("detects TST tasks", () => {
    expect(isTstTask(rows[0])).toBe(true);
    expect(isTstTask(rows[2])).toBe(true);
    expect(isTstTask(rows[3])).toBe(false);
  });

  it("filters high-priority unassigned", () => {
    const filtered = filterTaskRows(rows, "high_priority_unassigned");
    expect(filtered.map((r) => r.task_id)).toEqual(["a", "b"]);
  });

  it("filters by TST and High Priority sliders", () => {
    expect(filterBySliders(rows, { tst: true }).map((r) => r.task_id)).toEqual(["a", "c"]);
    expect(filterBySliders(rows, { highPriority: true }).map((r) => r.task_id)).toEqual(["a", "b"]);
    expect(filterBySliders(rows, { tst: true, highPriority: true }).map((r) => r.task_id)).toEqual([
      "a",
    ]);
    expect(filterBySliders(rows, {}).map((r) => r.task_id)).toEqual(["a", "b", "c", "d"]);
  });

  it("suggests auto filter for harness", () => {
    expect(suggestAutoFilter(rows, { harnessMode: true })).toBe("high_priority_unassigned");
    expect(suggestSliderState(rows, { harnessMode: true })).toEqual({
      tst: false,
      highPriority: true,
    });
  });

  it("suggests TST when no high-priority unassigned", () => {
    const onlyAssigned = rows.filter((r) => r.task_id === "c");
    expect(suggestAutoFilter(onlyAssigned)).toBe("tst");
    expect(suggestSliderState(onlyAssigned)).toEqual({ tst: true, highPriority: false });
  });

  it("counts filter buckets", () => {
    const counts = countByFilter(rows);
    expect(counts.tst).toBe(2);
    expect(counts.high_priority_unassigned).toBe(2);
    expect(countBySliders(rows)).toEqual({ tst: 2, highPriority: 2 });
  });

  it("detects high priority", () => {
    expect(isHighPriority(rows[0])).toBe(true);
    expect(isHighPriority(rows[3])).toBe(false);
  });
});
