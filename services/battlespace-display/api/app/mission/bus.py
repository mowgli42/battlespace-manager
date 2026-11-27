"""Redis fan-out for mission-management events (uci.mission.*).

Authoritative state remains SQLite. Bus publish is optional and best-effort.
Subscribe supports multi-instance sample/audit mirroring with idempotent inserts.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Callable

from app.mission.store import MissionStore, utc_now
from app.mission.topics import (
    SUBSCRIBE_TOPICS,
    TOPIC_MISSION_EVENT,
    TOPIC_MISSION_SAMPLE,
    topic_for_event_type,
)

logger = logging.getLogger("mission-bus")

_publisher: "MissionBusPublisher | None" = None
_subscriber_thread: threading.Thread | None = None
_stop = threading.Event()


def bus_enabled() -> bool:
    return os.getenv("MISSION_BUS_ENABLED", "").lower() in ("1", "true", "yes")


def bus_subscribe_enabled() -> bool:
    return os.getenv("MISSION_BUS_SUBSCRIBE", "").lower() in ("1", "true", "yes")


def _redis_url() -> str:
    return os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")


class MissionBusPublisher:
    def __init__(self, bus: Any | None = None) -> None:
        self._bus = bus
        self._lock = threading.Lock()
        self.published: list[dict[str, Any]] = []  # test spy when bus is None / memory

    def _ensure_bus(self) -> Any | None:
        if self._bus is not None:
            return self._bus
        if not bus_enabled():
            return None
        try:
            from uci_common.bus import RedisBus

            self._bus = RedisBus(_redis_url())
            return self._bus
        except Exception:
            logger.exception("Mission bus unavailable; publish skipped")
            return None

    def publish_event(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: str,
        actor_id: str,
        payload: dict[str, Any],
        event_id: str = "",
        reason: str = "",
        source: str = "battlespace-mission",
    ) -> dict[str, Any]:
        envelope = {
            "schema": "uci.mission.event/v1",
            "event_id": event_id or payload.get("event_id") or "",
            "event_type": event_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "actor_id": actor_id,
            "reason": reason,
            "source": source,
            "event_timestamp": payload.get("event_timestamp") or utc_now(),
            "received_timestamp": utc_now(),
            "payload": payload,
        }
        typed = topic_for_event_type(event_type, entity_type)
        body = json.dumps(envelope, default=str)
        with self._lock:
            self.published.append({"topic": typed, "envelope": envelope})
        bus = self._ensure_bus()
        if bus is None and not bus_enabled():
            return envelope
        if bus is None:
            return envelope
        try:
            bus.publish(typed, body)
            if typed != TOPIC_MISSION_EVENT:
                bus.publish(TOPIC_MISSION_EVENT, body)
        except Exception:
            logger.exception("Failed to publish mission event to %s", typed)
        return envelope


def get_publisher() -> MissionBusPublisher:
    global _publisher
    if _publisher is None:
        _publisher = MissionBusPublisher()
    return _publisher


def set_publisher_for_tests(publisher: MissionBusPublisher | None) -> None:
    global _publisher
    _publisher = publisher


def ingest_bus_message(store: MissionStore, topic: str, body: str) -> str:
    """Idempotently apply a peer mission bus message. Returns action taken."""
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("Ignoring non-JSON mission bus message on %s", topic)
        return "ignored_non_json"

    event_id = str(data.get("event_id") or "")
    event_type = str(data.get("event_type") or "")
    entity_type = str(data.get("entity_type") or "")
    entity_id = str(data.get("entity_id") or "")
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else data

    # Utilization samples (typed topic or sample event type)
    is_sample = topic == TOPIC_MISSION_SAMPLE or "sample" in event_type.lower()
    if is_sample:
        samples = payload.get("samples") if isinstance(payload.get("samples"), list) else None
        if samples is None and payload.get("platform_id"):
            samples = [payload]
        if not samples:
            # Audit-only sample notice without platform rows — fall through to audit mirror
            pass
        else:
            existing = {s.get("sample_id") for s in store.list_utilization_samples()}
            added = 0
            for raw in samples:
                sid = raw.get("sample_id")
                if not sid or sid in existing:
                    continue
                store.append_utilization_sample(dict(raw))
                existing.add(sid)
                added += 1
            return f"samples_added:{added}"

    # Audit mirror
    if event_id:
        for ev in store.list_audit(entity_type or None, entity_id or None):
            if ev.event_id == event_id:
                return "duplicate_audit"
        from app.mission.models import AuditEvent
        from app.mission.store import new_id

        store.append_audit(
            AuditEvent(
                event_id=event_id or new_id("EVT"),
                event_type=event_type or "bus.event",
                entity_type=entity_type or "unknown",
                entity_id=entity_id or "",
                actor_id=str(data.get("actor_id") or "bus"),
                event_timestamp=str(data.get("event_timestamp") or utc_now()),
                received_timestamp=utc_now(),
                previous_value=payload.get("previous_value"),
                new_value=payload.get("new_value", payload),
                reason=str(data.get("reason") or "bus_ingest"),
                source=f"bus:{topic}",
            )
        )
        return "audit_mirrored"
    return "ignored"


def start_mission_bus_subscriber(
    store_factory: Callable[[], MissionStore],
    *,
    bus: Any | None = None,
) -> threading.Thread | None:
    """Start a daemon thread that subscribes to uci.mission.* topics."""
    global _subscriber_thread
    if not bus_subscribe_enabled():
        logger.info("MISSION_BUS_SUBSCRIBE disabled")
        return None
    if _subscriber_thread and _subscriber_thread.is_alive():
        return _subscriber_thread

    _stop.clear()

    def _loop() -> None:
        try:
            local_bus = bus
            if local_bus is None:
                from uci_common.bus import RedisBus

                local_bus = RedisBus(_redis_url())
        except Exception:
            logger.exception("Cannot start mission bus subscriber")
            return

        def handler(topic: str, body: str) -> None:
            try:
                store = store_factory()
                action = ingest_bus_message(store, topic, body)
                logger.debug("Mission bus ingest %s → %s", topic, action)
            except Exception:
                logger.exception("Mission bus ingest failed for %s", topic)

        logger.info("Mission bus subscribing to %s", ", ".join(SUBSCRIBE_TOPICS))
        try:
            # RedisBus.subscribe blocks forever — run until process exit
            local_bus.subscribe(list(SUBSCRIBE_TOPICS), handler)
        except Exception:
            logger.exception("Mission bus subscriber exited")

    _subscriber_thread = threading.Thread(
        target=_loop, name="mission-bus-subscriber", daemon=True
    )
    _subscriber_thread.start()
    return _subscriber_thread


def stop_mission_bus_subscriber() -> None:
    _stop.set()
