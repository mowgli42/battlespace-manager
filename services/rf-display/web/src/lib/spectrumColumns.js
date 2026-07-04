/** Spectrum column helpers for four-column RF deconfliction view. */

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

export function assetBarStyle(asset, freqRange) {
  const [min, max] = freqRange || [0, 15000];
  const span = max - min || 1;
  const low = asset.freq_low_mhz ?? asset.frequency_mhz - (asset.bandwidth_mhz || 1) / 2;
  const high = asset.freq_high_mhz ?? asset.frequency_mhz + (asset.bandwidth_mhz || 1) / 2;
  const bottom = ((low - min) / span) * 100;
  const top = ((high - min) / span) * 100;
  const height = Math.max(3, top - bottom);
  return {
    bottom: `${Math.max(0, Math.min(97, bottom))}%`,
    height: `${Math.min(40, height)}%`,
  };
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
