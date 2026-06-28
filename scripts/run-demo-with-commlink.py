#!/usr/bin/env python3
"""Run ADS-B MVP + commlink-status on memory bus + entity-display API."""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

BM_ROOT = Path(__file__).resolve().parents[1]
OMY_ROOT = Path(os.environ.get("OMY_ROOT", BM_ROOT.parent / "o-my"))
sys.path.insert(0, str(OMY_ROOT / "packages/uci_common/src"))
sys.path.insert(0, str(BM_ROOT / "services/entity-display/api"))

os.environ.setdefault("REDIS_URL", "memory://")
os.environ.setdefault(
    "COMMLINK_DIRECTORY_XML",
    str(BM_ROOT / "fixtures/commlink-directory-v1.1.xml"),
)

import uvicorn  # noqa: E402

from uci_common import (  # noqa: E402
    CommlinkStatusEngine,
    RedisBus,
    TOPIC_COMMLINK_INVENTORY,
    TOPIC_COMMLINK_RESERVATION,
    TOPIC_COMMLINK_STATUS,
    TOPIC_ENTITY,
    TOPIC_ENTITY_NOTIFICATION,
    build_categorized_entity_xml,
    build_inventory_report_xml,
    build_reservation_report_xml,
    build_status_report_xml,
    build_track_report_xml,
    parse_directory_xml,
    parse_track_report_xml,
)
from uci_common.messages import CategorizedEntity  # noqa: E402
from uci_common.mock_feed import MockAdsbFeed  # noqa: E402

from app.main import app as display_app  # noqa: E402

bus = RedisBus()
feed = MockAdsbFeed()
_tick = 0


def _categorize(track_xml: str) -> CategorizedEntity:
    track = parse_track_report_xml(track_xml)
    alt = track.altitude_feet
    if alt >= 30000:
        primary, sub, tags = "High-Altitude-Commercial", "Passenger-Jet", ["Commercial", "Above-30000ft"]
    elif alt >= 10000:
        primary, sub, tags = "Mid-Altitude-Commercial", "Regional", ["Commercial", "10000-30000ft"]
    else:
        primary, sub, tags = "Low-Altitude", "General-Aviation", ["Low-Altitude", "Monitor"]
    threat = "Low"
    if track.squawk in ("7700", "7500", "7600"):
        threat = "High"
        tags = tags + [f"Squawk-{track.squawk}"]
    tags.append("Non-Threat" if threat == "Low" else "Alert")
    return CategorizedEntity(
        message_id="",
        reference_message_id=track.message_id,
        original_track_id=track.track_id,
        primary_category=primary,
        sub_category=sub,
        threat_level=threat,
        confidence=0.95 if threat == "Low" else 0.99,
        tags=tags,
        sort_criteria="Altitude + ICAO Category",
    )


def _sorter_loop() -> None:
    def handle(channel: str, xml_body: str) -> None:
        if channel != TOPIC_ENTITY:
            return
        bus.publish(TOPIC_ENTITY_NOTIFICATION, build_categorized_entity_xml(_categorize(xml_body)))

    bus.subscribe([TOPIC_ENTITY], handle)
    while True:
        time.sleep(3600)


def _sensor_loop() -> None:
    while True:
        for track in feed.generate():
            bus.publish(TOPIC_ENTITY, build_track_report_xml(track))
        time.sleep(3)


def _commlink_loop() -> None:
    global _tick
    xml_path = Path(os.environ["COMMLINK_DIRECTORY_XML"])
    document = parse_directory_xml(xml_path.read_text(encoding="utf-8"))
    engine = CommlinkStatusEngine(document)
    bus.publish(TOPIC_COMMLINK_INVENTORY, build_inventory_report_xml(engine.inventory_report()))
    for report in engine.reservation_reports():
        bus.publish(TOPIC_COMMLINK_RESERVATION, build_reservation_report_xml(report))
    interval = float(os.getenv("STATUS_INTERVAL_SEC", "5"))
    time.sleep(0.5)
    while True:
        _tick += 1
        for link in engine.document.comm_links:
            report = engine.status_report(link.id, _tick)
            if report is None:
                continue
            bus.publish(TOPIC_COMMLINK_STATUS, build_status_report_xml(report))
        time.sleep(interval)


def main() -> None:
    threading.Thread(target=_sorter_loop, daemon=True).start()
    threading.Thread(target=_sensor_loop, daemon=True).start()
    threading.Thread(target=_commlink_loop, daemon=True).start()
    print("Entity display demo (memory bus) on http://0.0.0.0:8003")
    uvicorn.run(display_app, host="0.0.0.0", port=8003, log_level="info")


if __name__ == "__main__":
    main()
