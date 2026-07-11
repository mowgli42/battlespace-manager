/** ITU nine-band radio spectrum helpers (mirrors api/app/rf_bands.py). */

export const ITU_BANDS = [
  { id: "vlf", number: 4, label: "VLF", name: "Very Low Frequency", freq_low_mhz: 0.003, freq_high_mhz: 0.03 },
  { id: "lf", number: 5, label: "LF", name: "Low Frequency", freq_low_mhz: 0.03, freq_high_mhz: 0.3 },
  { id: "mf", number: 6, label: "MF", name: "Medium Frequency", freq_low_mhz: 0.3, freq_high_mhz: 3 },
  { id: "hf", number: 7, label: "HF", name: "High Frequency", freq_low_mhz: 3, freq_high_mhz: 30 },
  { id: "vhf", number: 8, label: "VHF", name: "Very High Frequency", freq_low_mhz: 30, freq_high_mhz: 300 },
  { id: "uhf", number: 9, label: "UHF", name: "Ultra High Frequency", freq_low_mhz: 300, freq_high_mhz: 3000 },
  { id: "shf", number: 10, label: "SHF", name: "Super High Frequency", freq_low_mhz: 3000, freq_high_mhz: 30000 },
  { id: "ehf", number: 11, label: "EHF", name: "Extremely High Frequency", freq_low_mhz: 30000, freq_high_mhz: 300000 },
  { id: "thf", number: 12, label: "THF", name: "Tremendously High Frequency", freq_low_mhz: 300000, freq_high_mhz: 3000000 },
];

export function formatBandRange(lowMhz, highMhz) {
  if (highMhz < 1) return `${(lowMhz * 1000).toFixed(0)}–${(highMhz * 1000).toFixed(0)} kHz`;
  if (highMhz < 1000) return `${lowMhz < 1 ? lowMhz.toFixed(2) : Math.round(lowMhz)}–${Math.round(highMhz)} MHz`;
  if (highMhz < 1_000_000) return `${(lowMhz / 1000).toFixed(1)}–${(highMhz / 1000).toFixed(0)} GHz`;
  return `${(lowMhz / 1000).toFixed(0)}–${(highMhz / 1000).toFixed(0)} THz`;
}

export function bandOccupancyClass(band) {
  if (!band?.occupant_count) return "empty";
  if (band.jam_interaction_count > 0) return "jam";
  if (band.contested) return "contested";
  return "active";
}

export function interactionsForBand(interactions, bandId) {
  return (interactions || []).filter((i) => i.band_id === bandId);
}

export function normalizeDrilldown(interaction) {
  const devices = interaction?.devices || [];
  if (!devices.length) return interaction;
  const maxPower = Math.max(...devices.map((d) => d.power_level || 0.1), 0.1);
  const span =
    (interaction.freq_high_mhz || 0) - (interaction.freq_low_mhz || 0) ||
    Math.max(...devices.map((d) => d.channel_width_mhz || 1));
  return {
    ...interaction,
    channel_span_mhz: span,
    devices: devices.map((d) => ({
      ...d,
      channel_left_pct: span ? ((d.channel_low_mhz - interaction.freq_low_mhz) / span) * 100 : 0,
      channel_width_pct: span ? (d.channel_width_mhz / span) * 100 : 100,
      power_pct: (d.power_level / maxPower) * 100,
    })),
  };
}
