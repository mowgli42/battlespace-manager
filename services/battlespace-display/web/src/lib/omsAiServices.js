/** OMS AI recommendation service status helpers. */

export const SCOPE_LABELS = {
  entities: "Entities",
  targets: "Targets",
  tasks: "Tasks",
  platforms: "Platforms",
};

export function statusLabel(status) {
  if (status === "live") return "Live";
  if (status === "degraded") return "Degraded";
  if (status === "unconfigured") return "Unconfigured";
  return "Offline";
}

export function statusClass(status) {
  if (status === "live") return "live";
  if (status === "degraded") return "degraded";
  return "offline";
}

export function formatScopes(scopes) {
  return (scopes || []).map((s) => SCOPE_LABELS[s] || s).join(" · ");
}

export function anyLiveService(services) {
  return (services || []).some((s) => s.status === "live");
}

export function liveServiceCount(summary) {
  return summary?.live_count ?? (summary?.any_live ? 1 : 0);
}
