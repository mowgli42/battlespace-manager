import asyncio
import json
import logging
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.display_logic import build_feed_status_list, derive_affiliation
from app.detection_overlay import build_live_detection_overlays
from app.entity_harness import all_features_pass, build_harness_snapshot, verify_entity_features
from app.scenario_context import load_scenario, scenario_path
from uci_common import (
    RedisBus,
    TOPIC_COMMLINK_INVENTORY,
    TOPIC_COMMLINK_RESERVATION,
    TOPIC_COMMLINK_STATUS,
    TOPIC_CORRELATED_ENTITY,
    TOPIC_ENTITY,
    TOPIC_ENTITY_NOTIFICATION,
    build_commlink_display,
    commlink_stats,
    parse_categorized_entity_xml,
    parse_correlated_entity_xml,
    parse_directory_xml,
    parse_inventory_report_xml,
    parse_reservation_report_xml,
    parse_status_report_xml,
    parse_track_report_xml,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("entity-display-api")

app = FastAPI(title="Entity Display API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_portal_dir = Path(__file__).resolve().parents[3] / "display-portal"
try:
    from app.portal_routes import register_portal_routes
except ImportError:
    if _portal_dir.is_dir() and str(_portal_dir) not in sys.path:
        sys.path.insert(0, str(_portal_dir))
    from portal_routes import register_portal_routes  # noqa: E402

register_portal_routes(app, display_id="entity", title="Entity Display — OMS Portal")

_harness_mode = os.getenv("ENTITY_HARNESS", "").lower() in ("1", "true", "yes")
_overlay_mode = os.getenv("ENTITY_OVERLAYS", "auto").lower()

bus = RedisBus()

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_XML = _REPO_ROOT / "fixtures" / "commlink-directory-v1.1.xml"
_xml_path = Path(os.getenv("COMMLINK_DIRECTORY_XML", str(_DEFAULT_XML)))

OPERATOR_TAG_PRESETS = ("WATCH", "PROMOTE", "TASK", "ISR", "HOLD")

_FEED_REGISTRY: list[dict[str, str]] = [
    {"feed_id": "entity-fusion", "label": "Entity fusion", "type": "processor", "role": "correlation"},
    {"feed_id": "ads-b-sensor", "label": "ADS-B ingest", "type": "sensor", "role": "entity"},
    {"feed_id": "entity-sorter", "label": "Entity sorter", "type": "processor", "role": "category"},
    {"feed_id": "commlink-status", "label": "Commlink status", "type": "status", "role": "comms"},
    {"feed_id": "commlink-inventory", "label": "Commlink inventory", "type": "inventory", "role": "comms"},
    {"feed_id": "commlink-reservation", "label": "Commlink reservations", "type": "reservation", "role": "comms"},
]

_TOPIC_TO_FEED: dict[str, str] = {
    TOPIC_CORRELATED_ENTITY: "entity-fusion",
    TOPIC_ENTITY: "entity-sorter",
    TOPIC_ENTITY_NOTIFICATION: "entity-sorter",
    TOPIC_COMMLINK_STATUS: "commlink-status",
    TOPIC_COMMLINK_INVENTORY: "commlink-inventory",
    TOPIC_COMMLINK_RESERVATION: "commlink-reservation",
}


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
    operator_tags: list[str] = field(default_factory=list)
    promoted: bool = False
    entity_type: str = "aircraft"
    affiliation: str = "unknown"


_tracks: dict[str, TrackView] = {}
_commlink_statuses: dict[str, object] = {}
_commlink_reservations: dict[str, object] = {}
_feed_ticks: dict[str, dict[str, float | int]] = {}
_platforms_live: dict[str, dict[str, object]] = {}
_sim_minutes: float = 0.0
_scenario: dict | None = None
_directory = None
_lock = threading.Lock()


def _overlays_enabled() -> bool:
    if _harness_mode:
        return True
    if _overlay_mode in ("0", "false", "no", "off"):
        return False
    if _overlay_mode in ("1", "true", "yes", "on"):
        return True
    return scenario_path().is_file()


def _load_scenario() -> dict | None:
    global _scenario
    if _scenario is not None:
        return _scenario
    try:
        _scenario = load_scenario()
        logger.info("Loaded scenario for live overlays: %s", scenario_path())
    except Exception:
        logger.warning("No scenario for live overlays (%s)", scenario_path())
        _scenario = None
    return _scenario


def _detected_entity_ids() -> set[str]:
    return set(_tracks.keys())


def _build_live_overlays() -> dict:
    scenario = _load_scenario()
    if not scenario or not _overlays_enabled():
        return {
            "fog_zones": [],
            "route_corridors": [],
            "route_target_alerts": [],
            "summary": {},
        }
    return build_live_detection_overlays(
        scenario,
        platforms_live=_platforms_live,
        detected_entity_ids=_detected_entity_ids(),
        sim_minutes=_sim_minutes,
    )


def _refresh_track_derived(tv: TrackView) -> None:
    tv.affiliation = derive_affiliation(tv.threat_level, tv.tags, tv.squawk)
    tv.entity_type = "aircraft"


def _bump_feed(channel: str) -> None:
    feed_id = _TOPIC_TO_FEED.get(channel, channel)
    now = time.time()
    entry = _feed_ticks.setdefault(feed_id, {"count": 0, "last_seen": 0.0})
    entry["count"] = int(entry.get("count", 0)) + 1
    entry["last_seen"] = now


def _feed_status_list() -> list[dict]:
    return build_feed_status_list(_FEED_REGISTRY, _feed_ticks, now=time.time())


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


def _live_snapshot() -> dict:
    with _lock:
        tracks = []
        for t in _tracks.values():
            _refresh_track_derived(t)
            tracks.append(asdict(t))
        overlays = _build_live_overlays()
        map_view = None
        scenario = _scenario
        if scenario and scenario.get("bbox"):
            bbox = scenario["bbox"]
            map_view = {
                "center_lat": float(bbox.get("centerLat", 29.75)),
                "center_lon": float(bbox.get("centerLon", 47.75)),
                "zoom": 7,
            }
        return {
            "tracks": tracks,
            "commlinks": build_commlink_display(
                _load_directory(),
                dict(_commlink_statuses),
                dict(_commlink_reservations),
            ),
            "feed_status": _feed_status_list(),
            "overlays": overlays,
            "map_view": map_view,
            "harness_mode": False,
            "overlay_mode": _overlay_mode,
            "sim_minutes": _sim_minutes,
        }


def _snapshot_json() -> str:
    if _harness_mode:
        return json.dumps(build_harness_snapshot())
    return json.dumps(_live_snapshot())


def _on_message(channel: str, xml_body: str) -> None:
    try:
        with _lock:
            _bump_feed(channel)
            if channel == TOPIC_CORRELATED_ENTITY:
                ent = parse_correlated_entity_xml(xml_body)
                track_id = ent.entity_id
                existing = _tracks.get(track_id)
                _tracks[track_id] = TrackView(
                    track_id=track_id,
                    callsign=existing.callsign if existing else track_id,
                    latitude=ent.latitude,
                    longitude=ent.longitude,
                    altitude_feet=existing.altitude_feet if existing else 0.0,
                    heading_deg=existing.heading_deg if existing else 0.0,
                    ground_speed_kts=existing.ground_speed_kts if existing else 0.0,
                    squawk=existing.squawk if existing else "1200",
                    primary_category=existing.primary_category if existing else None,
                    sub_category=existing.sub_category if existing else None,
                    threat_level=existing.threat_level if existing else None,
                    tags=list(existing.tags) if existing else [],
                    operator_tags=list(existing.operator_tags) if existing else [],
                    promoted=existing.promoted if existing else False,
                )
                _refresh_track_derived(_tracks[track_id])
            elif channel == TOPIC_ENTITY:
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
                    operator_tags=list(existing.operator_tags) if existing else [],
                    promoted=existing.promoted if existing else False,
                )
                _refresh_track_derived(_tracks[t.track_id])
            elif channel == TOPIC_ENTITY_NOTIFICATION:
                c = parse_categorized_entity_xml(xml_body)
                if c.original_track_id in _tracks:
                    tv = _tracks[c.original_track_id]
                    tv.primary_category = c.primary_category
                    tv.sub_category = c.sub_category
                    tv.threat_level = c.threat_level
                    tv.tags = c.tags
                    _refresh_track_derived(tv)
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
            else:
                _on_overlay_message(channel, xml_body)
    except Exception:
        logger.exception("Failed to process bus message on %s", channel)


def _on_overlay_message(channel: str, xml_body: str) -> None:
    if not _overlays_enabled():
        return
    try:
        from app.omysim_bridge import (
            parse_platform_status_xml,
            parse_scenario_clock_xml,
            topic_platform_status,
            topic_scenario_clock,
        )

        if channel == topic_platform_status():
            report = parse_platform_status_xml(xml_body)
            subs = getattr(report, "subsystems", {}) or {}
            _platforms_live[report.platform_id] = {
                "platform_id": report.platform_id,
                "callsign": report.callsign,
                "latitude": report.latitude,
                "longitude": report.longitude,
                "readiness": report.readiness,
                "radar_online": subs.get("radar", "ONLINE") == "ONLINE",
            }
        elif channel == topic_scenario_clock():
            global _sim_minutes
            _sim_minutes = float(parse_scenario_clock_xml(xml_body).sim_minutes)
    except Exception:
        logger.exception("Failed to process overlay bus message on %s", channel)


def _subscriber_loop() -> None:
    topics = [
        TOPIC_CORRELATED_ENTITY,
        TOPIC_ENTITY,
        TOPIC_ENTITY_NOTIFICATION,
        TOPIC_COMMLINK_INVENTORY,
        TOPIC_COMMLINK_STATUS,
        TOPIC_COMMLINK_RESERVATION,
    ]
    if _overlays_enabled():
        try:
            from app.omysim_bridge import topic_platform_status, topic_scenario_clock

            topics.extend([topic_platform_status(), topic_scenario_clock()])
        except Exception:
            logger.exception("Overlay topics unavailable — platform/scenario clock disabled")
    logger.info("Subscribing to %s", ", ".join(topics))
    bus.subscribe(topics, _on_message)


@app.on_event("startup")
def startup() -> None:
    try:
        _load_directory()
    except Exception:
        logger.exception("Failed to load commlink directory XML")
    if _harness_mode:
        logger.info("ENTITY_HARNESS=1 — serving deterministic overlay scenario")
        return
    if _overlays_enabled():
        _load_scenario()
        logger.info("Live detection overlays enabled (mode=%s)", _overlay_mode)
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
            "harness_mode": _harness_mode,
            "overlay_mode": _overlay_mode,
            "overlays_enabled": _overlays_enabled(),
            "scenario_loaded": _scenario is not None,
            "platform_count": len(_platforms_live),
            "sim_minutes": _sim_minutes,
            "tracks": n,
            "directory_version": document.version,
            "commlink_status_messages": status_count,
            "xml_source": str(_xml_path),
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "service": "entity-display-api",
            "harness_mode": _harness_mode,
            "tracks": n,
            "error": str(exc),
        }


@app.get("/api/overlays")
def get_overlays() -> dict:
    if _harness_mode:
        snap = build_harness_snapshot()
        return {"overlays": snap.get("overlays"), "harness_mode": True}
    with _lock:
        overlays = _build_live_overlays()
        sim = _sim_minutes
    return {"overlays": overlays, "harness_mode": False, "sim_minutes": sim}


@app.get("/api/harness/verify")
def harness_verify() -> dict:
    snapshot = build_harness_snapshot() if _harness_mode else _live_snapshot()
    results = verify_entity_features(snapshot)
    return {"passed": all_features_pass(results), "harness_mode": _harness_mode, "checks": results}


@app.get("/api/tracks")
def list_tracks() -> dict:
    with _lock:
        tracks = []
        for t in _tracks.values():
            _refresh_track_derived(t)
            tracks.append(asdict(t))
        return {"tracks": tracks}


@app.get("/api/feeds")
def list_feeds() -> dict:
    with _lock:
        return {"feeds": _feed_status_list()}


@app.get("/api/commlinks")
def list_commlinks() -> dict:
    return _commlink_display()


@app.get("/api/stats")
def stats() -> dict:
    with _lock:
        tracks = list(_tracks.values())
        for t in tracks:
            _refresh_track_derived(t)
    by_cat: dict[str, int] = {}
    by_aff: dict[str, int] = {"friendly": 0, "hostile": 0, "unknown": 0}
    alerts = 0
    promoted = 0
    for t in tracks:
        cat = t.primary_category or "Uncategorized"
        by_cat[cat] = by_cat.get(cat, 0) + 1
        by_aff[t.affiliation] = by_aff.get(t.affiliation, 0) + 1
        if t.threat_level == "High" or t.squawk in ("7700", "7500", "7600"):
            alerts += 1
        if t.promoted:
            promoted += 1
    display = _commlink_display()
    with _lock:
        feeds = _feed_status_list()
    return {
        "total": len(tracks),
        "by_category": by_cat,
        "by_affiliation": by_aff,
        "alerts": alerts,
        "promoted": promoted,
        "commlinks": commlink_stats(display),
        "feed_status": feeds,
    }


@app.post("/api/tracks/{track_id}/tags")
def add_operator_tag(track_id: str, body: dict) -> dict:
    tag = (body.get("tag") or "").strip().upper()
    if not tag:
        raise HTTPException(400, "tag required")
    with _lock:
        tv = _tracks.get(track_id)
        if not tv:
            raise HTTPException(404, f"Track {track_id} not found")
        if tag not in tv.operator_tags:
            tv.operator_tags.append(tag)
        return {"status": "ok", "track": asdict(tv)}


@app.delete("/api/tracks/{track_id}/tags/{tag}")
def remove_operator_tag(track_id: str, tag: str) -> dict:
    tag = tag.strip().upper()
    with _lock:
        tv = _tracks.get(track_id)
        if not tv:
            raise HTTPException(404, f"Track {track_id} not found")
        tv.operator_tags = [t for t in tv.operator_tags if t != tag]
        if tag == "PROMOTE":
            tv.promoted = False
        return {"status": "ok", "track": asdict(tv)}


@app.post("/api/tracks/{track_id}/promote")
def promote_track(track_id: str, body: dict | None = None) -> dict:
    body = body or {}
    with _lock:
        tv = _tracks.get(track_id)
        if not tv:
            raise HTTPException(404, f"Track {track_id} not found")
        promoted = body.get("promoted")
        if promoted is None:
            tv.promoted = not tv.promoted
        else:
            tv.promoted = bool(promoted)
        if tv.promoted and "PROMOTE" not in tv.operator_tags:
            tv.operator_tags.append("PROMOTE")
        elif not tv.promoted:
            tv.operator_tags = [t for t in tv.operator_tags if t != "PROMOTE"]
        return {"status": "ok", "track": asdict(tv)}


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
