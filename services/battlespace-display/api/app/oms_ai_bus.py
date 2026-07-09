"""UCI bus caches for OMS AI services (advisor suggestions + service status)."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from uci_common.bus import RedisBus

logger = logging.getLogger("oms-ai-bus")

try:
    from uci_common.agent_messages import parse_agent_suggestion_xml
    from uci_common.topics import TOPIC_AGENT_SUGGESTION
except ImportError:
    TOPIC_AGENT_SUGGESTION = "uci.agent.suggestion"

    def parse_agent_suggestion_xml(xml_body: str) -> Any:
        raise ValueError("agent suggestion parser unavailable")


class OmsAiBusCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._suggestions: dict[str, dict[str, Any]] = {}
        self._isr_assignments: list[dict[str, Any]] = []
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def ingest(self, channel: str, xml_body: str) -> None:
        if channel != TOPIC_AGENT_SUGGESTION:
            return
        try:
            sug = parse_agent_suggestion_xml(xml_body)
            row = {
                "suggestion_id": sug.suggestion_id,
                "target_entity_id": sug.target_entity_id,
                "target_name": sug.target_name,
                "suggested_role": sug.suggested_role,
                "priority": sug.priority,
                "reason": sug.reason,
                "status": "open",
                "source_service": "mission-advisor",
                "requires_approval": sug.requires_approval,
            }
            with self._lock:
                self._suggestions[sug.suggestion_id] = row
                if sug.suggested_role.upper() in ("ISR", "ISR_COLLECTION", "RECON"):
                    self._isr_assignments.append(
                        {
                            "suggestion_id": sug.suggestion_id,
                            "target_entity_id": sug.target_entity_id,
                            "role": sug.suggested_role,
                        }
                    )
                    self._isr_assignments = self._isr_assignments[-50:]
        except Exception:
            logger.exception("Failed to ingest advisor suggestion")

    def suggestions(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._suggestions.values())

    def isr_assignments(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._isr_assignments)


_cache: OmsAiBusCache | None = None
_started = False


def oms_ai_bus_cache() -> OmsAiBusCache:
    global _cache
    if _cache is None:
        _cache = OmsAiBusCache()
    return _cache


def bus_advisor_enabled() -> bool:
    return os.getenv("ADVISOR_BUS", "1").lower() not in ("0", "false", "no", "off")


def start_oms_ai_bus_subscriber(redis_url: str | None = None) -> bool:
    global _started
    if not bus_advisor_enabled() or _started:
        return _started
    url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    if url.startswith("memory://"):
        return False
    cache = oms_ai_bus_cache()
    bus = RedisBus(url)

    def _loop() -> None:
        try:
            logger.info("OMS AI bus subscribing to %s", TOPIC_AGENT_SUGGESTION)
            bus.subscribe([TOPIC_AGENT_SUGGESTION], cache.ingest)
        except Exception:
            logger.exception("OMS AI bus subscribe failed")

    threading.Thread(target=_loop, daemon=True).start()
    cache._connected = True
    _started = True
    return True
