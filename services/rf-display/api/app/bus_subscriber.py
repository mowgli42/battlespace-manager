"""Redis bus ingestion for live EMSO / spectrum / commlink updates."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from app.omy_bridge import parse_emso_conflict_xml, parse_spectrum_analytics_xml
from uci_common.bus import RedisBus
from uci_common.commlink_messages import (
    parse_inventory_report_xml,
    parse_reservation_report_xml,
    parse_status_report_xml,
)
from uci_common.topics import (
    TOPIC_COMMLINK_INVENTORY,
    TOPIC_COMMLINK_RESERVATION,
    TOPIC_COMMLINK_STATUS,
)

TOPIC_EMSO_CONFLICT = "uci.emso.conflict"
TOPIC_ANALYTICS_SPECTRUM = "uci.analytics.spectrum"

logger = logging.getLogger("rf-display-bus")

RefreshFn = Callable[[], None]


class RfBusSubscriber:
    def __init__(self, bus: RedisBus, on_refresh: RefreshFn) -> None:
        self._bus = bus
        self._on_refresh = on_refresh
        self._lock = threading.Lock()
        self._commlink_statuses: dict[str, object] = {}
        self._commlink_reservations: dict[str, object] = {}
        self._emso_conflicts: list[dict[str, Any]] = []
        self._spectrum_analytics: dict[str, Any] | None = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def commlink_statuses(self) -> dict[str, object]:
        with self._lock:
            return dict(self._commlink_statuses)

    def commlink_reservations(self) -> dict[str, object]:
        with self._lock:
            return dict(self._commlink_reservations)

    def emso_conflicts(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._emso_conflicts)

    def spectrum_analytics(self) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._spectrum_analytics) if self._spectrum_analytics else None

    def _on_message(self, channel: str, xml_body: str) -> None:
        try:
            with self._lock:
                if channel == TOPIC_COMMLINK_STATUS:
                    report = parse_status_report_xml(xml_body)
                    self._commlink_statuses[report.link_id] = report
                elif channel == TOPIC_COMMLINK_RESERVATION:
                    report = parse_reservation_report_xml(xml_body)
                    self._commlink_reservations[report.reservation_id] = report
                elif channel == TOPIC_COMMLINK_INVENTORY:
                    inv = parse_inventory_report_xml(xml_body)
                    logger.info("Inventory bus update v%s (%d links)", inv.directory_version, inv.link_count)
                elif channel == TOPIC_EMSO_CONFLICT:
                    report = parse_emso_conflict_xml(xml_body)
                    row = {
                        "conflict_id": report.conflict_id,
                        "severity": report.severity,
                        "resource_id": report.resource_id,
                        "reservation_ids": report.reservation_ids,
                        "frequency_mhz": report.frequency_mhz,
                        "overlap_start": report.overlap_start,
                        "overlap_end": report.overlap_end,
                        "recommendation": report.recommendation,
                    }
                    self._emso_conflicts = [c for c in self._emso_conflicts if c["conflict_id"] != row["conflict_id"]]
                    self._emso_conflicts.append(row)
                    self._emso_conflicts = self._emso_conflicts[-50:]
                elif channel == TOPIC_ANALYTICS_SPECTRUM:
                    report = parse_spectrum_analytics_xml(xml_body)
                    self._spectrum_analytics = {
                        "active_links": report.active_links,
                        "total_links": report.total_links,
                        "utilization_pct": report.utilization_pct,
                        "contested_links": report.contested_links,
                        "frequency_bands_in_use": report.frequency_bands_in_use,
                        "links": report.link_rows,
                    }
            self._on_refresh()
        except Exception:
            logger.exception("Bus message failed on %s", channel)

    def start(self) -> bool:
        topics = [
            TOPIC_COMMLINK_INVENTORY,
            TOPIC_COMMLINK_STATUS,
            TOPIC_COMMLINK_RESERVATION,
            TOPIC_EMSO_CONFLICT,
            TOPIC_ANALYTICS_SPECTRUM,
        ]
        try:
            logger.info("RF display subscribing to %s", ", ".join(topics))
            threading.Thread(target=lambda: self._bus.subscribe(topics, self._on_message), daemon=True).start()
            self._connected = True
            return True
        except Exception:
            logger.exception("Redis bus subscribe failed — embedded mode only")
            self._connected = False
            return False
