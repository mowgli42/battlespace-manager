/** CAOC task row filters — TST and high-priority sliders. */

const TERMINAL = new Set(["EXECUTED", "ABORTED"]);

export function isTaskUnassigned(row) {
  const lc = row.lifecycle_state || "NEW";
  if (TERMINAL.has(lc)) return false;
  return !row.assigned_platform_id;
}

export function isHighPriority(row, maxPriority = 2) {
  return Number(row.priority ?? 99) <= maxPriority;
}

/** Match Decisions TST strip + Attention TST kind: time-sensitive, not terminal. */
export function isTstTask(row) {
  return Boolean(row.is_time_sensitive) && !TERMINAL.has(row.lifecycle_state || "NEW");
}

/** @deprecated Prefer slider flags; kept for tests migrating off chip ids. */
export const TASK_FILTERS = [
  { id: "all", label: "All" },
  { id: "tst", label: "TST" },
  { id: "unassigned", label: "Unassigned" },
  { id: "high_priority_unassigned", label: "High priority · unassigned" },
];

/**
 * Filter queue by slider toggles.
 * TST on → time-sensitive only.
 * High Priority on → high-priority unassigned (actionable queue work).
 * Both on → intersection. Both off → all rows.
 */
export function filterBySliders(rows, { tst = false, highPriority = false } = {}) {
  return rows.filter((r) => {
    if (tst && !isTstTask(r)) return false;
    if (highPriority && !(isTaskUnassigned(r) && isHighPriority(r))) return false;
    return true;
  });
}

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

/** Default slider state when harness loads or focus clears. */
export function suggestSliderState(rows, { harnessMode = false } = {}) {
  if (harnessMode) return { tst: false, highPriority: true };
  const hpUnassigned = rows.filter((r) => isTaskUnassigned(r) && isHighPriority(r));
  if (hpUnassigned.length > 0) return { tst: false, highPriority: true };
  const tst = rows.filter(isTstTask);
  if (tst.length > 0) return { tst: true, highPriority: false };
  return { tst: false, highPriority: false };
}

/** @deprecated Prefer suggestSliderState. */
export function suggestAutoFilter(rows, { harnessMode = false } = {}) {
  const s = suggestSliderState(rows, { harnessMode });
  if (s.highPriority) return "high_priority_unassigned";
  if (s.tst) return "tst";
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

export function countBySliders(rows) {
  return {
    tst: rows.filter(isTstTask).length,
    highPriority: rows.filter((r) => isTaskUnassigned(r) && isHighPriority(r)).length,
  };
}
