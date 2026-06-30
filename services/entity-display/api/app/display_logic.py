"""Pure display logic (testable without Redis / uci_common)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TrackViewLite:
    threat_level: str | None = None
    tags: list[str] = field(default_factory=list)
    squawk: str = "1200"


def derive_affiliation(
    threat_level: str | None,
    tags: list[str],
    squawk: str = "1200",
) -> str:
    if threat_level == "High" or "Alert" in tags or squawk in ("7700", "7500", "7600"):
        return "hostile"
    if "Non-Threat" in tags or "Commercial" in tags:
        return "friendly"
    return "unknown"


def build_feed_status_list(
    registry: list[dict[str, str]],
    feed_ticks: dict[str, dict[str, float | int]],
    *,
    now: float,
    stale_after_s: float = 30.0,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for meta in registry:
        fid = meta["feed_id"]
        tick = feed_ticks.get(fid, {})
        last = float(tick.get("last_seen", 0))
        age = now - last if last else None
        active = age is not None and age < stale_after_s
        out.append(
            {
                **meta,
                "active": active,
                "message_count": int(tick.get("count", 0)),
                "last_seen_age_s": round(age, 1) if age is not None else None,
                "status": "live" if active else ("stale" if last else "idle"),
            }
        )
    return out
