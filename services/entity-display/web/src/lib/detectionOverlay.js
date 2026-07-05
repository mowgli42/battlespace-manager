/** Styles and helpers for detection overlay map layers. */

export const OVERLAY_DEFAULTS = {
  fog: true,
  routes: true,
  alerts: true,
};

export function fogStyle(zone) {
  return {
    color: "#64748b",
    weight: 1,
    dashArray: "6 4",
    fillColor: "#0f172a",
    fillOpacity: zone.opacity ?? 0.5,
  };
}

export function routeStyle(corridor) {
  const pattern = corridor.pattern || "";
  if (pattern === "orbit") {
    return { color: "#38bdf8", weight: 2, opacity: 0.85, dashArray: "4 6" };
  }
  if (pattern === "racetrack") {
    return { color: "#a78bfa", weight: 2, opacity: 0.85, dashArray: "8 4" };
  }
  return { color: "#34d399", weight: 3, opacity: 0.9 };
}

export function routeTooltip(corridor) {
  return `${corridor.callsign} · ${corridor.route_name || corridor.pattern} · ${corridor.buffer_nm} nm buffer`;
}

export function alertStyle(alert) {
  return {
    radius: alert.in_fog ? 10 : 8,
    color: alert.in_fog ? "#fbbf24" : "#f472b6",
    fillColor: alert.in_fog ? "#fbbf24" : "#f472b6",
    weight: 2,
    fillOpacity: 0.35,
    className: alert.in_fog ? "route-alert-fog" : "route-alert",
  };
}

export function alertTooltip(alert) {
  const fog = alert.in_fog ? " · in fog" : "";
  return `Route alert: ${alert.target_label} · ${alert.callsign} passes within ${alert.buffer_nm} nm${fog}`;
}

export function overlaySummaryText(summary) {
  if (!summary || !summary.fog_zone_count) return "";
  return `${summary.fog_zone_count} fog · ${summary.route_corridor_count} routes · ${summary.route_target_alert_count} alerts`;
}
