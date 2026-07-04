"""Terrain-aware RF propagation helpers for jam envelope sizing (FSPL)."""

from __future__ import annotations

import math


def fspl_db(distance_km: float, freq_mhz: float) -> float:
    """Free-space path loss in dB (distance km, frequency MHz)."""
    d = max(distance_km, 0.001)
    f = max(freq_mhz, 0.001)
    return 20.0 * math.log10(d) + 20.0 * math.log10(f) + 32.44


def distance_km_for_fspl(target_fspl_db: float, freq_mhz: float) -> float:
    """Solve FSPL equation for distance (km) at a given frequency."""
    f = max(freq_mhz, 0.001)
    exponent = (target_fspl_db - 20.0 * math.log10(f) - 32.44) / 20.0
    return 10.0**exponent


def terrain_mask_factor(altitude_feet: float) -> float:
    """Simplified terrain masking: low-altitude jammers lose horizon range."""
    if altitude_feet >= 25000:
        return 1.0
    if altitude_feet >= 10000:
        return 0.85
    if altitude_feet >= 5000:
        return 0.65
    return 0.45


def jam_effective_coverage_nm(
    *,
    frequency_mhz: float,
    altitude_feet: float = 35000.0,
    eirp_dbm: float = 62.0,
    receiver_threshold_dbm: float = -92.0,
    min_nm: float = 15.0,
    max_nm: float = 120.0,
) -> dict[str, float]:
    """
    Estimate standoff jamming envelope radius (nautical miles).

    Uses FSPL with a terrain mask on altitude; returns nominal and effective radii.
    """
    freq = max(frequency_mhz, 1.0)
    max_loss_db = eirp_dbm - receiver_threshold_dbm
    dist_km = distance_km_for_fspl(max_loss_db, freq)
    dist_nm = dist_km / 1.852
    mask = terrain_mask_factor(altitude_feet)
    effective = max(min_nm, min(max_nm, dist_nm * mask))
    return {
        "nominal_coverage_nm": round(dist_nm, 1),
        "effective_coverage_nm": round(effective, 1),
        "terrain_mask_factor": round(mask, 2),
        "fspl_at_effective_db": round(fspl_db(effective * 1.852, freq), 1),
    }
