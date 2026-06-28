import {
  ForceSideSchema,
  PictureEntitySchema,
  TrackSchema,
  type ForceSide,
  type PictureEntity,
  type Track,
} from "../types/track.js";

const AFFILIATION_FORCE: Record<string, ForceSide> = {
  COALITION: "friendly",
  FRIENDLY: "friendly",
  BLUE: "friendly",
  OPFOR: "hostile",
  HOSTILE: "hostile",
  RED: "hostile",
  NEUTRAL: "neutral",
  UNKNOWN: "unknown",
};

export function affiliationToForce(affiliation: string | undefined): ForceSide {
  if (!affiliation) return "unknown";
  const key = affiliation.trim().toUpperCase();
  return AFFILIATION_FORCE[key] ?? ForceSideSchema.parse("unknown");
}

export function entityToTrack(raw: unknown, simMinutes?: number): Track {
  const entity: PictureEntity = PictureEntitySchema.parse(raw);
  return TrackSchema.parse({
    id: entity.entity_id,
    force: affiliationToForce(entity.affiliation),
    lat: entity.latitude,
    lon: entity.longitude,
    timestamp: simMinutes,
    metadata: {
      domain: entity.domain,
      platform_type: entity.platform_type,
      confidence: entity.confidence,
      altitude_feet: entity.altitude_feet,
      sources: entity.sources,
      affiliation: entity.affiliation,
    },
  });
}

export function entitiesToTracks(entities: unknown[], simMinutes?: number): Track[] {
  return entities.map((e) => entityToTrack(e, simMinutes));
}
