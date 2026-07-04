/** Spectrum column helpers for four-column RF deconfliction view. */

export { assetBarStyle, createFreqScale, freqTicks } from "./spectrumScale.js";

export const COLUMN_META = {
  threat_radars: { color: "var(--hostile)", icon: "◆" },
  jammers: { color: "var(--jam)", icon: "⚡" },
  comm: { color: "var(--comm)", icon: "◎" },
  support: { color: "var(--friendly)", icon: "◇" },
};

export function overlapClass(conflictType) {
  if (conflictType === "jam_comm" || conflictType === "jam_support" || conflictType === "jrfl_violation") {
    return "overlap-jam-critical";
  }
  if (conflictType === "jam_radar") return "overlap-jam-radar";
  if (conflictType === "band_overlap") return "overlap-band";
  return "overlap-other";
}

export function isJammed(asset) {
  return (asset.jammed_by || []).length > 0;
}

export function isJamming(asset) {
  return asset.jamming_active && (asset.jamming_targets || []).length > 0;
}

export function formatFreq(mhz) {
  if (mhz == null) return "—";
  if (mhz >= 1000) return `${(mhz / 1000).toFixed(2)} GHz`;
  return `${mhz.toFixed(mhz < 10 ? 2 : 1)} MHz`;
}
