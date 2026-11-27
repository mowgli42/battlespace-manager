"""Background continuous utilization sampler.

When ``MISSION_SAMPLER_ENABLED=1``, a daemon thread periodically snapshots
fleet utilization into SQLite (and optionally publishes ``uci.mission.sample``).
Does not invent readiness — samples use the same picture/org join as the API.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Callable

logger = logging.getLogger("mission-sampler")

_thread: threading.Thread | None = None
_stop = threading.Event()


def sampler_enabled() -> bool:
    return os.getenv("MISSION_SAMPLER_ENABLED", "").lower() in ("1", "true", "yes")


def sampler_interval_seconds() -> float:
    raw = os.getenv("MISSION_SAMPLER_INTERVAL_SECONDS", "900")
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 900.0


def start_continuous_sampler(
    service_factory: Callable[[], Any],
    picture_provider: Callable[[], dict[str, Any]] | None = None,
) -> threading.Thread | None:
    """Start daemon sampler if enabled. Idempotent."""
    global _thread
    if not sampler_enabled():
        logger.info("MISSION_SAMPLER_ENABLED disabled")
        return None
    if _thread is not None and _thread.is_alive():
        return _thread

    _stop.clear()
    interval = sampler_interval_seconds()

    def _loop() -> None:
        logger.info("Continuous utilization sampler started (interval=%ss)", interval)
        # Initial delay so startup picture/subscribers can settle
        if _stop.wait(min(interval, 2.0)):
            return
        while not _stop.is_set():
            try:
                svc = service_factory()
                picture = picture_provider() if picture_provider else {}
                result = svc.analytics.record_fleet_sample(picture, actor_id="system:sampler")
                # Audit + bus fan-out via service helper when available
                if hasattr(svc, "_audit"):
                    svc._audit(
                        event_type="analytics.sample_recorded",
                        entity_type="fleet",
                        entity_id="fleet",
                        actor_id="system:sampler",
                        previous_value=None,
                        new_value={
                            "sample_count": result.get("sample_count"),
                            "sampled_at": result.get("sampled_at"),
                            "source": "continuous_sampler",
                        },
                        reason="continuous_sampler",
                        source="mission-sampler",
                    )
                try:
                    from app.mission.bus import get_publisher
                    from app.mission.topics import TOPIC_MISSION_SAMPLE

                    pub = get_publisher()
                    envelope = {
                        "schema": "uci.mission.sample/v1",
                        "event_type": "analytics.sample_recorded",
                        "entity_type": "fleet",
                        "entity_id": "fleet",
                        "actor_id": "system:sampler",
                        "source": "mission-sampler",
                        "samples": result.get("samples") or [],
                        "sampled_at": result.get("sampled_at"),
                        "sample_count": result.get("sample_count"),
                    }
                    # Prefer typed publish via publisher API
                    pub.publish_event(
                        event_type="analytics.sample_recorded",
                        entity_type="fleet",
                        entity_id="fleet",
                        actor_id="system:sampler",
                        reason="continuous_sampler",
                        source="mission-sampler",
                        payload=envelope,
                    )
                    # Ensure samples key is on the typed topic even if umbrella-only peers listen
                    _ = TOPIC_MISSION_SAMPLE
                except Exception:
                    logger.exception("Sampler bus publish failed")
                logger.info(
                    "Utilization sample recorded: %s platforms at %s",
                    result.get("sample_count"),
                    result.get("sampled_at"),
                )
            except Exception:
                logger.exception("Continuous sampler tick failed")
            if _stop.wait(interval):
                break
        logger.info("Continuous utilization sampler stopped")

    _thread = threading.Thread(target=_loop, name="mission-utilization-sampler", daemon=True)
    _thread.start()
    return _thread


def stop_continuous_sampler() -> None:
    _stop.set()


def reset_sampler_for_tests() -> None:
    global _thread
    stop_continuous_sampler()
    _thread = None
    _stop.clear()
