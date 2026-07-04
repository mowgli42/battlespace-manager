/** CAOC task row filters — TST and unassigned high-priority targets. */

const TERMINAL = new Set(["EXECUTED", "ABORTED"]);

export function isTaskUnassigned(row) {
  const lc = row.lifecycle_state || "NEW";
  if (TERMINAL.has(lc)) return false;
  return !row.assigned_platform_id;
}

export function isHighPriority(row, maxPriority = 2) {
  return Number(row.priority ?? 99) <= maxPriority;
}

export function isTstTask(row) {
  return Boolean(row.is_time_sensitive) && !TERMINAL.has(row.lifecycle_state || "NEW");
}

export const TASK_FILTERS = [
  { id: "all", label: "All" },
  { id: "tst", label: "TST" },
  { id: "unassigned", label: "Unassigned" },
  { id: "high_priority_unassigned", label: "High priority · unassigned" },
];

export function filterTaskRows(rows, filterId) {
  switch (filterId) {
    case "tst":
      return rows.filter(isTstTask);
    case "unassigned":
      return rows.filter(isTaskUnassigned);
    case "high_priority_unassigned":
      return rows.filter((r) => isTaskUnassigned(r) && isHighPriority(r));
    default:
      return rows;
  }
}

/** Pick default filter when TST or unassigned high-priority tasks need operator focus. */
export function suggestAutoFilter(rows, { harnessMode = false } = {}) {
  if (harnessMode) return "high_priority_unassigned";
  const hpUnassigned = rows.filter((r) => isTaskUnassigned(r) && isHighPriority(r));
  if (hpUnassigned.length > 0) return "high_priority_unassigned";
  const tst = rows.filter(isTstTask);
  if (tst.length > 0) return "tst";
  const unassigned = rows.filter(isTaskUnassigned);
  if (unassigned.length > 0) return "unassigned";
  return "all";
}

export function countByFilter(rows) {
  return {
    all: rows.length,
    tst: rows.filter(isTstTask).length,
    unassigned: rows.filter(isTaskUnassigned).length,
    high_priority_unassigned: rows.filter((r) => isTaskUnassigned(r) && isHighPriority(r)).length,
  };
}
