/** Frequency band labels for spectrum occupancy display. */
export function bandLabel(mhz) {
  if (mhz < 30) return "HF";
  if (mhz < 300) return "VHF/UHF";
  if (mhz < 2000) return "L-band";
  if (mhz < 4000) return "S-band";
  if (mhz < 8000) return "C-band";
  if (mhz < 12000) return "X-band";
  if (mhz < 20000) return "Ku-band";
  return "Ka+";
}

export function conflictSeverityClass(severity) {
  if (severity === "high") return "severity-high";
  if (severity === "medium") return "severity-medium";
  return "severity-low";
}

export function conflictTypeLabel(type) {
  const labels = {
    jam_comm: "Jam ↔ Comms",
    jam_radar: "Jam ↔ Radar",
    emcon_violation: "EMCON",
    reservation_conflict: "Reservation",
    jrfl_violation: "JRFL",
  };
  return labels[type] || type;
}
