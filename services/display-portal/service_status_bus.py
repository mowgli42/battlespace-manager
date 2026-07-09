"""Subscribe to uci.service.status for display health panels."""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from uci_common.bus import RedisBus
from uci_common.service_messages import parse_service_status_xml
from uci_common.topics import TOPIC_SERVICE_STATUS

logger = logging.getLogger("service-status-bus")

_STALE_SEC = float(os.getenv("SERVICE_STATUS_STALE_SEC", "120"))


class ServiceStatusCache:
    """Thread-safe cache of latest uci.service.status per service name."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rows: dict[str, dict[str, Any]] = {}
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def ingest(self, channel: str, xml_body: str) -> None:
        if channel != TOPIC_SERVICE_STATUS:
            return
        try:
            msg = parse_service_status_xml(xml_body)
            if not msg.name:
                return
            row = {
                "name": msg.name,
                "enabled": msg.enabled,
                "health": msg.health,
                "maturity_level": msg.maturity_level,
                "version": msg.version,
                "detail": msg.detail,
                "topics": list(msg.topics),
                "last_seen_ms": int(time.time() * 1000),
            }
            with self._lock:
                self._rows[msg.name] = row
        except Exception:
            logger.exception("Failed to parse service status on %s", channel)

    def get(self, name: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._rows.get(name)
            return dict(row) if row else None

    def all_rows(self) -> list[dict[str, Any]]:
        now_ms = int(time.time() * 1000)
        with self._lock:
            rows = []
            for row in self._rows.values():
                copy = dict(row)
                age_ms = now_ms - int(copy.get("last_seen_ms", 0))
                copy["stale"] = age_ms > int(_STALE_SEC * 1000)
                rows.append(copy)
            return sorted(rows, key=lambda r: r.get("name", ""))

    def probe_status(self, service_name: str) -> dict[str, Any] | None:
        """Map bus health to display portal status vocabulary."""
        row = self.get(service_name)
        if row is None:
            return None
        health = str(row.get("health") or "healthy").lower()
        if not row.get("enabled", True):
            status = "degraded"
            detail = row.get("detail") or "disabled"
        elif health in ("healthy", "ok", "live"):
            status = "live"
            detail = row.get("detail") or health
        elif health in ("degraded",):
            status = "degraded"
            detail = row.get("detail") or health
        else:
            status = "offline"
            detail = row.get("detail") or health
        if row.get("stale"):
            status = "degraded" if status == "live" else status
            detail = f"{detail}; bus status stale"
        return {
            "status": status,
            "detail": detail,
            "source": "uci.service.status",
            "bus_row": row,
        }


_cache: ServiceStatusCache | None = None
_subscriber_started = False


def service_status_cache() -> ServiceStatusCache:
    global _cache
    if _cache is None:
        _cache = ServiceStatusCache()
    return _cache


def bus_status_enabled() -> bool:
    return os.getenv("SERVICE_STATUS_BUS", "1").lower() not in ("0", "false", "no", "off")


def start_service_status_subscriber(redis_url: str | None = None) -> bool:
    """Start background subscriber when SERVICE_STATUS_BUS is enabled."""
    global _subscriber_started
    if not bus_status_enabled() or _subscriber_started:
        return _subscriber_started
    url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    if url.startswith("memory://"):
        return False
    cache = service_status_cache()
    bus = RedisBus(url)

    def _loop() -> None:
        try:
            logger.info("Subscribing to %s", TOPIC_SERVICE_STATUS)
            bus.subscribe([TOPIC_SERVICE_STATUS], cache.ingest)
        except Exception:
            logger.exception("Service status bus subscribe failed")

    threading.Thread(target=_loop, daemon=True).start()
    cache._connected = True
    _subscriber_started = True
    return True
