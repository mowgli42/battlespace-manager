/** CAOC task row sort: TST first, then priority, then recency. */

export function sortTaskRows(list) {
  return [...list].sort((a, b) => {
    const tst = Number(b.is_time_sensitive) - Number(a.is_time_sensitive);
    if (tst !== 0) return tst;
    const pri = Number(a.priority ?? 9) - Number(b.priority ?? 9);
    if (pri !== 0) return pri;
    return Number(b.assigned_at_sim ?? 0) - Number(a.assigned_at_sim ?? 0);
  });
}
