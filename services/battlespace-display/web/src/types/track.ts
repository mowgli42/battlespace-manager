import { z } from "zod";

/** APP-6 / MIL-STD-2525 force affiliation for symbology. */
export const ForceSideSchema = z.enum(["friendly", "hostile", "neutral", "unknown"]);
export type ForceSide = z.infer<typeof ForceSideSchema>;

export const TrackSchema = z.object({
  id: z.string().min(1),
  sidc: z.string().optional(),
  force: ForceSideSchema,
  lat: z.number().finite(),
  lon: z.number().finite(),
  heading: z.number().finite().optional(),
  speed: z.number().finite().optional(),
  timestamp: z.number().finite().optional(),
  metadata: z.record(z.unknown()).optional(),
});

export type Track = z.infer<typeof TrackSchema>;

/** Raw entity row from GET /api/picture `entities[]`. */
export const PictureEntitySchema = z
  .object({
    entity_id: z.string().min(1),
    latitude: z.number().finite(),
    longitude: z.number().finite(),
    affiliation: z.string().optional(),
    domain: z.string().optional(),
    platform_type: z.string().optional(),
    confidence: z.number().finite().optional(),
    altitude_feet: z.number().finite().optional(),
    sources: z.array(z.string()).optional(),
  })
  .passthrough();

export type PictureEntity = z.infer<typeof PictureEntitySchema>;
