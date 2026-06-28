import ms from "milsymbol";
import L from "leaflet";
import { getSidc, sidcCacheKey, type PictureEntityLike } from "./sidc.js";

const iconCache = new Map<string, L.Icon>();

export function createMilIcon(entity: PictureEntityLike, size = 28, selected = false): L.Icon {
  const sidc = getSidc(entity);
  const symbol = new ms.Symbol(sidc, {
    size: selected ? size + 4 : size,
  });
  const dim = selected ? size + 4 : size;
  return L.icon({
    iconUrl: symbol.toDataURL(),
    iconSize: [dim, dim],
    iconAnchor: [dim / 2, dim / 2],
    popupAnchor: [0, -dim / 2],
    className: selected ? "mil-symbol mil-symbol-selected" : "mil-symbol",
  });
}

export function getOrCreateMilIcon(entity: PictureEntityLike, selected = false): L.Icon {
  const key = `${sidcCacheKey(entity)}|${selected ? "sel" : "norm"}`;
  if (!iconCache.has(key)) {
    iconCache.set(key, createMilIcon(entity, 28, selected));
  }
  return iconCache.get(key)!;
}

export function entityPopupHtml(entity: PictureEntityLike & { entity_id?: string; latitude?: number; longitude?: number; confidence?: number }): string {
  const conf = entity.confidence != null ? `${Math.round(entity.confidence * 100)}%` : "—";
  return [
    `<strong>${entity.platform_type || entity.entity_id || "Track"}</strong>`,
    `${entity.affiliation || "—"} · ${entity.domain || "—"}`,
    `Confidence ${conf}`,
    `SIDC <code>${getSidc(entity)}</code>`,
  ].join("<br/>");
}

/** Test helper */
export function clearIconCache(): void {
  iconCache.clear();
}
