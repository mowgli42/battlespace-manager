import asyncio
import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from uci_common import (
    RedisBus,
    TOPIC_COMMLINK_INVENTORY,
    TOPIC_COMMLINK_RESERVATION,
    TOPIC_COMMLINK_STATUS,
    TOPIC_ENTITY,
    TOPIC_ENTITY_NOTIFICATION,
    build_commlink_display,
    commlink_stats,
    parse_categorized_entity_xml,
    parse_directory_xml,
    parse_inventory_report_xml,
    parse_reservation_report_xml,
    parse_status_report_xml,
    parse_track_report_xml,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("entity-display-api")

app = FastAPI(title="Entity Display API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bus = RedisBus()

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_XML = _REPO_ROOT / "fixtures" / "commlink-directory-v1.1.xml"
_xml_path = Path(os.getenv("COMMLINK_DIRECTORY_XML", str(_DEFAULT_XML)))


@dataclass
class TrackView:
    track_id: str
    callsign: str
    latitude: float
    longitude: float
    altitude_feet: float
    heading_deg: float
    ground_speed_kts: float
    squawk: str = "1200"
    primary_category: str | None = None
    sub_category: str | None = None
    threat_level: str | None = None
    tags: list[str] = field(default_factory=list)


_tracks: dict[str, TrackView] = {}
_commlink_statuses: dict[str, object] = {}
_commlink_reservations: dict[str, object] = {}
_directory = None
_lock = threading.Lock()


def _load_directory():
    global _directory
    if _directory is not None:
        return _directory
    if not _xml_path.is_file():
        raise FileNotFoundError(f"Directory XML not found: {_xml_path}")
    _directory = parse_directory_xml(_xml_path.read_text(encoding="utf-8"))
    logger.info(
        "Loaded Directory %s: %d contacts, %d links",
        _directory.version,
        len(_directory.contacts),
        len(_directory.comm_links),
    )
    return _directory


def _commlink_display() -> dict:
    document = _load_directory()
    with _lock:
        statuses = dict(_commlink_statuses)
        reservations = dict(_commlink_reservations)
    return build_commlink_display(document, statuses, reservations)


def _snapshot_json() -> str:
    with _lock:
        payload = {
            "tracks": [asdict(t) for t in _tracks.values()],
            "commlinks": build_commlink_display(
                _load_directory(),
                dict(_commlink_statuses),
                dict(_commlink_reservations),
            ),
        }
    return json.dumps(payload)


def _on_message(channel: str, xml_body: str) -> None:
    try:
        with _lock:
            if channel == TOPIC_ENTITY:
                t = parse_track_report_xml(xml_body)
                existing = _tracks.get(t.track_id)
                _tracks[t.track_id] = TrackView(
                    track_id=t.track_id,
                    callsign=t.callsign.strip(),
                    latitude=t.latitude,
                    longitude=t.longitude,
                    altitude_feet=t.altitude_feet,
                    heading_deg=t.heading_deg,
                    ground_speed_kts=t.ground_speed_kts,
                    squawk=t.squawk,
                    primary_category=existing.primary_category if existing else None,
                    sub_category=existing.sub_category if existing else None,
                    threat_level=existing.threat_level if existing else None,
                    tags=list(existing.tags) if existing else [],
                )
            elif channel == TOPIC_ENTITY_NOTIFICATION:
                c = parse_categorized_entity_xml(xml_body)
                if c.original_track_id in _tracks:
                    tv = _tracks[c.original_track_id]
                    tv.primary_category = c.primary_category
                    tv.sub_category = c.sub_category
                    tv.threat_level = c.threat_level
                    tv.tags = c.tags
            elif channel == TOPIC_COMMLINK_STATUS:
                report = parse_status_report_xml(xml_body)
                _commlink_statuses[report.link_id] = report
            elif channel == TOPIC_COMMLINK_RESERVATION:
                report = parse_reservation_report_xml(xml_body)
                _commlink_reservations[report.reservation_id] = report
            elif channel == TOPIC_COMMLINK_INVENTORY:
                inv = parse_inventory_report_xml(xml_body)
                logger.info(
                    "Inventory update: v%s, %d links",
                    inv.directory_version,
                    inv.link_count,
                )
    except Exception:
        logger.exception("Failed to process bus message on %s", channel)


def _subscriber_loop() -> None:
    topics = [
        TOPIC_ENTITY,
        TOPIC_ENTITY_NOTIFICATION,
        TOPIC_COMMLINK_INVENTORY,
        TOPIC_COMMLINK_STATUS,
        TOPIC_COMMLINK_RESERVATION,
    ]
    logger.info("Subscribing to %s", ", ".join(topics))
    bus.subscribe(topics, _on_message)


@app.on_event("startup")
def startup() -> None:
    try:
        _load_directory()
    except Exception:
        logger.exception("Failed to load commlink directory XML")
    threading.Thread(target=_subscriber_loop, daemon=True).start()


@app.get("/health")
def health() -> dict:
    with _lock:
        n = len(_tracks)
        status_count = len(_commlink_statuses)
    try:
        document = _load_directory()
        return {
            "status": "healthy",
            "service": "entity-display-api",
            "tracks": n,
            "directory_version": document.version,
            "commlink_status_messages": status_count,
            "xml_source": str(_xml_path),
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "service": "entity-display-api",
            "tracks": n,
            "error": str(exc),
        }


@app.get("/api/tracks")
def list_tracks() -> dict:
    with _lock:
        return {"tracks": [asdict(t) for t in _tracks.values()]}


@app.get("/api/commlinks")
def list_commlinks() -> dict:
    return _commlink_display()


@app.get("/api/stats")
def stats() -> dict:
    with _lock:
        tracks = list(_tracks.values())
    by_cat: dict[str, int] = {}
    alerts = 0
    for t in tracks:
        cat = t.primary_category or "Uncategorized"
        by_cat[cat] = by_cat.get(cat, 0) + 1
        if t.threat_level == "High" or t.squawk in ("7700", "7500", "7600"):
            alerts += 1
    display = _commlink_display()
    return {
        "total": len(tracks),
        "by_category": by_cat,
        "alerts": alerts,
        "commlinks": commlink_stats(display),
    }


@app.get("/api/stream")
async def stream() -> StreamingResponse:
    async def gen():
        last = ""
        while True:
            payload = _snapshot_json()
            if payload != last:
                last = payload
                yield f"data: {payload}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream")
