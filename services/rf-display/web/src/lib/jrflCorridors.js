/** JRFL protected-band corridor helpers. */

import { bandStyle } from "./spectrumScale.js";

export function jrflCorridorBounds(entry) {
  const freq = Number(entry.frequency_mhz);
  const bw = Number(entry.bandwidth_mhz || 1);
  const low = freq - bw / 2;
  const high = freq + bw / 2;
  return { low, high, freq };
}

export function buildJrflCorridors(entries, scale) {
  return (entries || []).map((entry) => {
    const { low, high, freq } = jrflCorridorBounds(entry);
    return {
      id: entry.id,
      label: entry.label,
      restriction: entry.restriction,
      frequency_mhz: freq,
      style: bandStyle(low, high, scale),
    };
  });
}

export function corridorRestrictionClass(restriction) {
  if (restriction === "NO_EA") return "jrfl-no-ea";
  if (restriction === "EA_REQUIRES_EACA") return "jrfl-eaca";
  return "jrfl-other";
}
