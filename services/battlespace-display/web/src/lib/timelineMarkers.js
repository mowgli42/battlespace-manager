/** o-my-debrief marker glyphs (Timeline.svelte / api.markerGlyph). */

export function markerGlyph(marker) {
  if (marker === "diamond") return "◆";
  if (marker === "caret") return "▼";
  if (marker === "flag") return "⚑";
  if (marker === "circle") return "●";
  return "·";
}

export function markerColor(marker) {
  if (marker === "diamond") return "#4da3ff";
  if (marker === "caret") return "#ff7a45";
  if (marker === "flag") return "#5ddea0";
  if (marker === "circle") return "#fbbf24";
  return "#8fa3c1";
}

export function markerLabel(marker) {
  if (marker === "diamond") return "collect / ISR";
  if (marker === "caret") return "strike";
  if (marker === "flag") return "on-station / launch";
  if (marker === "circle") return "threat";
  return "event";
}
