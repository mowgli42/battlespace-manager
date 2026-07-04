/** SVG connector geometry for cross-column spectrum overlaps. */

import { overlapClass } from "./spectrumColumns.js";

export const COLUMN_ORDER = ["threat_radars", "jammers", "comm", "support"];

const CONNECTOR_COLORS = {
  "overlap-jam-critical": "#f87171",
  "overlap-jam-radar": "#f59e0b",
  "overlap-band": "#64748b",
  "overlap-other": "#8fa3c7",
};

export function filterConnectorBands(overlapBands, { jamOnly = true } = {}) {
  return (overlapBands || []).filter((band) => {
    if (!band?.asset_ids || band.asset_ids.length < 2) return false;
    if (!jamOnly) return true;
    return String(band.conflict_type || "").startsWith("jam_");
  });
}

export function connectorPath(x1, y1, x2, y2) {
  const cx = x1 + (x2 - x1) * 0.5;
  return `M ${x1} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}`;
}

export function connectorStrokeClass(conflictType) {
  return overlapClass(conflictType);
}

export function connectorStrokeColor(conflictType) {
  return CONNECTOR_COLORS[overlapClass(conflictType)] || CONNECTOR_COLORS["overlap-other"];
}

/**
 * Resolve pixel endpoints for a pair of assets inside the spectrum grid.
 * @param {DOMRect} gridRect - bounding rect of the grid wrapper
 * @param {Map<string, DOMRect>} assetRects - key `${column}:${asset_id}`
 * @param {string} colA
 * @param {string} idA
 * @param {string} colB
 * @param {string} idB
 */
export function connectorEndpoints(gridRect, assetRects, colA, idA, colB, idB) {
  const rectA = assetRects.get(`${colA}:${idA}`);
  const rectB = assetRects.get(`${colB}:${idB}`);
  if (!rectA || !rectB) return null;

  const idxA = COLUMN_ORDER.indexOf(colA);
  const idxB = COLUMN_ORDER.indexOf(colB);
  const [left, right] = idxA <= idxB ? [rectA, rectB] : [rectB, rectA];

  const x1 = left.right - gridRect.left;
  const x2 = right.left - gridRect.left;
  const y1 = left.top + left.height / 2 - gridRect.top;
  const y2 = right.top + right.height / 2 - gridRect.top;

  if (x2 <= x1) return null;
  return { x1, y1, x2, y2 };
}

export function buildConnectorModels(overlapBands, gridRect, assetRects, options = {}) {
  const bands = filterConnectorBands(overlapBands, options);
  const models = [];

  for (const band of bands) {
    const epA = band.endpoints?.[0];
    const epB = band.endpoints?.[1];
    const idA = epA?.asset_id ?? band.asset_ids?.[0];
    const idB = epB?.asset_id ?? band.asset_ids?.[1];
    const colA = epA?.column ?? band.columns?.[0];
    const colB = epB?.column ?? band.columns?.[1];
    if (!idA || !idB || !colA || !colB) continue;

    const endpoints = connectorEndpoints(gridRect, assetRects, colA, idA, colB, idB);
    if (!endpoints) continue;

    const key = `${colA}:${idA}::${colB}:${idB}:${band.conflict_type}`;
    models.push({
      key,
      path: connectorPath(endpoints.x1, endpoints.y1, endpoints.x2, endpoints.y2),
      conflictType: band.conflict_type,
      strokeClass: connectorStrokeClass(band.conflict_type),
      strokeColor: connectorStrokeColor(band.conflict_type),
      assetIds: [idA, idB],
      columns: [colA, colB],
      frequencyMhz: band.frequency_mhz,
    });
  }
  return models;
}

export function connectorHighlightState(model, selectedAsset, hoveredKey) {
  if (hoveredKey) return model.key === hoveredKey ? "active" : "dim";
  if (!selectedAsset) return "normal";
  const hit =
    model.assetIds.includes(selectedAsset.asset_id) &&
    model.columns.includes(selectedAsset.column);
  return hit ? "active" : "dim";
}
