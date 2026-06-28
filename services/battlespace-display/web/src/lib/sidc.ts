/** MIL-STD-2525 / APP-6 SIDC helpers (Grok Q1). */

export type PictureEntityLike = {
  affiliation?: string;
  domain?: string;
  platform_type?: string;
};

const AFFIL: Record<string, string> = {
  OPFOR: "H",
  HOSTILE: "H",
  COALITION: "F",
  FRIENDLY: "F",
  NEUTRAL: "N",
  UNKNOWN: "U",
  PENDING: "U",
};

const DOMAIN: Record<string, string> = {
  AIR: "A",
  SURFACE: "G",
  GROUND: "G",
  SUBSURFACE: "U",
};

function norm(value: string | undefined): string {
  return (value || "").trim().toUpperCase();
}

/** 15-char SIDC string for milsymbol. */
export function getSidc(entity: PictureEntityLike): string {
  const aff = AFFIL[norm(entity.affiliation)] || "U";
  const dim = DOMAIN[norm(entity.domain)] || "G";
  const base = `S${aff}${dim}P`;

  const pt = norm(entity.platform_type);
  if (pt.includes("SA-") || pt.includes("SAM") || pt.includes("SCUD")) {
    return `${base}E-----------`;
  }

  return `${base}-----------`;
}

export function sidcCacheKey(entity: PictureEntityLike): string {
  return `${norm(entity.affiliation)}|${norm(entity.domain)}|${norm(entity.platform_type)}`;
}
