/** Derive affiliation from sorter tags and threat signals. */
export function trackAffiliation(track) {
  if (!track) return "unknown";
  if (
    track.threat_level === "High" ||
    track.tags?.includes("Alert") ||
    ["7700", "7500", "7600"].includes(track.squawk)
  ) {
    return "hostile";
  }
  if (track.tags?.includes("Non-Threat") || track.tags?.includes("Commercial")) {
    return "friendly";
  }
  return "unknown";
}

export function isMoving(track, thresholdKts = 30) {
  return (track.ground_speed_kts ?? 0) > thresholdKts;
}

export function isAircraft(track) {
  return track.entity_type !== "static";
}

export function matchesFilters(track, filters) {
  const aff = trackAffiliation(track);
  if (filters.affiliation !== "all" && aff !== filters.affiliation) return false;
  if (filters.kinematic === "moving" && !isMoving(track)) return false;
  if (filters.kinematic === "static" && isMoving(track)) return false;
  if (filters.entityType === "aircraft" && !isAircraft(track)) return false;
  if (filters.entityType === "static" && isAircraft(track)) return false;
  if (filters.taggedOnly && !(track.operator_tags?.length || track.promoted)) return false;
  return true;
}

export function filterTracks(tracks, filters) {
  return (tracks || []).filter((t) => matchesFilters(t, filters));
}
