"""RF deconfliction: jam-vs-comms, jam-vs-radar, EMCON violations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def bands_overlap(
    freq_a: float,
    bw_a: float,
    freq_b: float,
    bw_b: float,
    *,
    margin_mhz: float = 0.5,
) -> bool:
    low_a, high_a = freq_a - bw_a / 2 - margin_mhz, freq_a + bw_a / 2 + margin_mhz
    low_b, high_b = freq_b - bw_b / 2 - margin_mhz, freq_b + bw_b / 2 + margin_mhz
    return low_a <= high_b and low_b <= high_a


def _point_in_polygon(lat: float, lon: float, polygon: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon (lat=y, lon=x)."""
    inside = False
    n = len(polygon)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i]
        yj, xj = polygon[j]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside


@dataclass
class RfConflict:
    conflict_id: str
    conflict_type: str
    severity: str
    summary: str
    recommendation: str
    frequency_mhz: float | None
    involved_ids: list[str]
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type,
            "severity": self.severity,
            "summary": self.summary,
            "recommendation": self.recommendation,
            "frequency_mhz": self.frequency_mhz,
            "involved_ids": self.involved_ids,
            "details": self.details,
        }


def detect_rf_conflicts(
    *,
    comm_links: list[dict[str, Any]],
    emitters: list[dict[str, Any]],
    ew_platforms: list[dict[str, Any]],
    emcon_areas: list[dict[str, Any]],
    emso_conflicts: list[dict[str, Any]] | None = None,
    jrfl_entries: list[dict[str, Any]] | None = None,
    ea_authority: dict[str, Any] | None = None,
    support_assets: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return sorted RF conflicts for operator display."""
    conflicts: list[RfConflict] = []
    counter = 0
    authorized_roles = set((ea_authority or {}).get("authorized_roles") or [])

    friendly_comms = [
        l
        for l in comm_links
        if l.get("frequency_mhz") and l.get("status") in ("active", "degraded", "unknown")
    ]
    hostile_radars = [e for e in emitters if e.get("emitter_class") == "radar" and e.get("affiliation") == "hostile"]
    active_jammers = [p for p in ew_platforms if p.get("jamming_active")]
    support_assets: list[dict[str, Any]] = list(support_assets or [])

    for jammer in active_jammers:
        j_freq = float(jammer.get("frequency_mhz") or 0)
        j_bw = float(jammer.get("bandwidth_mhz") or 100)
        if j_freq <= 0:
            continue
        for link in friendly_comms:
            l_freq = float(link["frequency_mhz"])
            l_bw = float(link.get("bandwidth_mhz") or 1)
            if not bands_overlap(j_freq, j_bw, l_freq, l_bw):
                continue
            counter += 1
            conflicts.append(
                RfConflict(
                    conflict_id=f"rf-jam-comm-{counter:03d}",
                    conflict_type="jam_comm",
                    severity="high",
                    summary=f"{jammer.get('callsign', jammer['platform_id'])} jam overlaps {link.get('link_id', 'comm')}",
                    recommendation="shift_jam_band_or_reassign_comm_frequency",
                    frequency_mhz=l_freq,
                    involved_ids=[jammer["platform_id"], link.get("link_id", "")],
                    details={
                        "jammer_callsign": jammer.get("callsign"),
                        "link_type": link.get("type"),
                        "link_subtype": link.get("subtype"),
                    },
                )
            )

    for jammer in active_jammers:
        j_freq = float(jammer.get("frequency_mhz") or 0)
        j_bw = float(jammer.get("bandwidth_mhz") or 100)
        if j_freq <= 0:
            continue
        for radar in hostile_radars:
            r_freq = float(radar.get("frequency_mhz") or 0)
            r_bw = float(radar.get("bandwidth_mhz") or 10)
            if r_freq <= 0:
                continue
            if not bands_overlap(j_freq, j_bw, r_freq, r_bw):
                continue
            counter += 1
            conflicts.append(
                RfConflict(
                    conflict_id=f"rf-jam-radar-{counter:03d}",
                    conflict_type="jam_radar",
                    severity="medium",
                    summary=f"Jam on {radar.get('label', radar['emitter_type'])} — verify EACA and JRFL",
                    recommendation="confirm_eaca_authority_and_collateral_check",
                    frequency_mhz=r_freq,
                    involved_ids=[jammer["platform_id"], radar.get("emitter_id", "")],
                    details={
                        "target_radar": radar.get("label"),
                        "jammer_callsign": jammer.get("callsign"),
                    },
                )
            )

    for jammer in active_jammers:
        j_freq = float(jammer.get("frequency_mhz") or 0)
        j_bw = float(jammer.get("bandwidth_mhz") or 100)
        if j_freq <= 0:
            continue
        for asset in support_assets:
            s_freq = float(asset.get("frequency_mhz") or 0)
            s_bw = float(asset.get("bandwidth_mhz") or 1)
            if s_freq <= 0:
                continue
            if not bands_overlap(j_freq, j_bw, s_freq, s_bw):
                continue
            counter += 1
            support_kind = asset.get("support_kind", asset.get("emitter_class", "support"))
            conflicts.append(
                RfConflict(
                    conflict_id=f"rf-jam-support-{counter:03d}",
                    conflict_type="jam_support",
                    severity="high",
                    summary=f"{jammer.get('callsign', jammer['platform_id'])} jam threatens {asset.get('label', asset.get('asset_id'))}",
                    recommendation="shift_jam_band_or_protect_support_rf",
                    frequency_mhz=s_freq,
                    involved_ids=[jammer["platform_id"], asset.get("asset_id", "")],
                    details={
                        "support_kind": support_kind,
                        "support_label": asset.get("label"),
                        "jammer_callsign": jammer.get("callsign"),
                    },
                )
            )

    for emitter in emitters:
        lat = emitter.get("latitude")
        lon = emitter.get("longitude")
        if lat is None or lon is None:
            continue
        e_class = emitter.get("emitter_class", "")
        for area in emcon_areas:
            polygon = area.get("polygon") or []
            if not _point_in_polygon(float(lat), float(lon), polygon):
                continue
            restrictions = area.get("restrictions") or []
            violation = False
            if e_class == "radar" and "no_radar" in restrictions:
                violation = True
            if e_class == "jammer" and "no_active_jam" in restrictions:
                violation = True
            if e_class == "comm" and "no_hf" in restrictions and "HF" in str(emitter.get("band", "")):
                violation = True
            if not violation:
                continue
            counter += 1
            conflicts.append(
                RfConflict(
                    conflict_id=f"rf-emcon-{counter:03d}",
                    conflict_type="emcon_violation",
                    severity="high",
                    summary=f"{emitter.get('label', emitter.get('emitter_type'))} violates {area.get('name')}",
                    recommendation="cease_emission_or_exit_emcon_area",
                    frequency_mhz=emitter.get("frequency_mhz"),
                    involved_ids=[emitter.get("emitter_id", ""), area.get("id", "")],
                    details={
                        "emcon_posture": area.get("posture"),
                        "restrictions": restrictions,
                    },
                )
            )

    for emso in emso_conflicts or []:
        counter += 1
        conflicts.append(
            RfConflict(
                conflict_id=emso.get("conflict_id") or f"rf-emso-{counter:03d}",
                conflict_type="reservation_conflict",
                severity=emso.get("severity", "medium"),
                summary=f"Reservation overlap on {emso.get('resource_id', 'resource')}",
                recommendation=emso.get("recommendation", "deconflict_frequency"),
                frequency_mhz=emso.get("frequency_mhz"),
                involved_ids=list(emso.get("reservation_ids") or []),
                details={"overlap_start": emso.get("overlap_start"), "overlap_end": emso.get("overlap_end")},
            )
        )

    for entry in jrfl_entries or []:
        freq = float(entry.get("frequency_mhz") or 0)
        bw = float(entry.get("bandwidth_mhz") or 1)
        if freq <= 0:
            continue
        restriction = entry.get("restriction", "")
        for jammer in active_jammers:
            j_freq = float(jammer.get("frequency_mhz") or 0)
            j_bw = float(jammer.get("bandwidth_mhz") or 100)
            if j_freq <= 0 or not bands_overlap(j_freq, j_bw, freq, bw):
                continue
            task_role = (jammer.get("task_role") or "").upper()
            authorized = task_role in authorized_roles if authorized_roles else False
            if restriction == "NO_EA":
                severity = "high"
                rec = "cease_jam_immediately_jrfl_protected"
            elif restriction == "EA_REQUIRES_EACA" and not authorized:
                severity = "high"
                rec = "obtain_eaca_before_jamming_jrfl_freq"
            elif restriction == "EA_REQUIRES_EACA" and authorized:
                continue
            else:
                severity = "medium"
                rec = "verify_jrfl_guidance"
            counter += 1
            conflicts.append(
                RfConflict(
                    conflict_id=f"rf-jrfl-{counter:03d}",
                    conflict_type="jrfl_violation",
                    severity=severity,
                    summary=f"{jammer.get('callsign', jammer['platform_id'])} jam threatens JRFL {entry.get('label', entry.get('id'))}",
                    recommendation=rec,
                    frequency_mhz=freq,
                    involved_ids=[jammer["platform_id"], entry.get("id", "")],
                    details={
                        "jrfl_restriction": restriction,
                        "jrfl_mission": entry.get("mission"),
                        "ea_authority": ea_authority.get("level") if ea_authority else None,
                    },
                )
            )

    severity_order = {"high": 0, "medium": 1, "low": 2}
    conflicts.sort(key=lambda c: (severity_order.get(c.severity, 9), c.conflict_type))
    return [c.to_dict() for c in conflicts]
