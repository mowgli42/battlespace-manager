import { describe, expect, it } from "vitest";
import {
  countByFilter,
  filterTaskRows,
  isHighPriority,
  isTaskUnassigned,
  isTstTask,
  suggestAutoFilter,
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

  it("suggests auto filter for harness", () => {
    expect(suggestAutoFilter(rows, { harnessMode: true })).toBe("high_priority_unassigned");
  });

  it("suggests TST when no high-priority unassigned", () => {
    const onlyAssigned = rows.filter((r) => r.task_id === "c");
    expect(suggestAutoFilter(onlyAssigned)).toBe("tst");
  });

  it("counts filter buckets", () => {
    const counts = countByFilter(rows);
    expect(counts.tst).toBe(2);
    expect(counts.high_priority_unassigned).toBe(2);
  });

  it("detects high priority", () => {
    expect(isHighPriority(rows[0])).toBe(true);
    expect(isHighPriority(rows[3])).toBe(false);
  });
});
