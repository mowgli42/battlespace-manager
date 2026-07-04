from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.bus_subscriber import RfBusSubscriber
from app.geo_filter import apply_geo_filter, validate_geo_filter
from app.omy_bridge import build_commlink_display, emso_deconfliction_engine
from app.rf_harness import build_harness_picture, verify_rf_features
from app.rf_picture_contract import assert_rf_picture_contract, build_rf_picture
from uci_common.bus import RedisBus
from uci_common.commlink_messages import parse_reservation_report_xml, parse_status_report_xml
from uci_common.directory_xml import parse_directory_xml

if TYPE_CHECKING:
    from uci_common.gulfwar_engine import GulfWarEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rf-display-api")

app = FastAPI(title="RF Display API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_XML = _REPO_ROOT / "fixtures" / "commlink-directory-v1.1.xml"
_xml_path = Path(os.getenv("COMMLINK_DIRECTORY_XML", str(_DEFAULT_XML)))
_REDIS_URL = os.getenv("REDIS_URL", "memory://")

_engine: GulfWarEngine | None = None
_lock = threading.Lock()
_commlink_statuses: dict[str, object] = {}
_commlink_reservations: dict[str, object] = {}
_directory = None
_emso_engine: EmsoDeconflictionEngine | None = None
_picture_cache: dict[str, Any] = {}
_highlight_entity_id: str | None = None
_bus: RedisBus | None = None
_bus_subscriber: RfBusSubscriber | None = None
_geo_filter: dict[str, Any] | None = None
_harness_mode = os.getenv("RF_HARNESS", "").lower() in ("1", "true", "yes")


class HighlightBody(BaseModel):
    entity_id: str


class GeoFilterBody(BaseModel):
    type: str
    active: bool = True
    label: str = ""
    geometry: dict[str, Any]
    include_non_geo: bool = False


def _load_directory():
    global _directory, _emso_engine
    if _directory is not None:
        return _directory
    if not _xml_path.is_file():
        raise FileNotFoundError(f"Directory XML not found: {_xml_path}")
    _directory = parse_directory_xml(_xml_path.read_text(encoding="utf-8"))
    _emso_engine = emso_deconfliction_engine(document=_directory)
    logger.info("Loaded commlink directory v%s (%d links)", _directory.version, len(_directory.comm_links))
    return _directory


def set_engine(engine: GulfWarEngine) -> None:
    global _engine
    _engine = engine


def _conflict_to_dict(report: Any) -> dict[str, Any]:
    return {
        "conflict_id": report.conflict_id,
        "severity": report.severity,
        "resource_id": report.resource_id,
        "reservation_ids": report.reservation_ids,
        "frequency_mhz": report.frequency_mhz,
        "overlap_start": report.overlap_start,
        "overlap_end": report.overlap_end,
        "recommendation": report.recommendation,
    }


def _fixture_emso_conflicts() -> list[dict[str, Any]]:
    directory = _load_directory()
    engine = emso_deconfliction_engine(document=directory)
    conflicts: list[dict[str, Any]] = []
    for resv in directory.reservations:
        from uci_common.commlink_messages import CommLinkReservationReport

        found = engine.ingest_reservation_report(
            CommLinkReservationReport(
                message_id="",
                reservation_id=resv.id,
                resource_id=resv.resource_id,
                link_id=resv.link_id,
                status=resv.status,
                priority=resv.priority,
                mission=resv.mission,
                window_start=resv.window_start,
                window_end=resv.window_end,
            )
        )
        for c in found:
            conflicts.append(_conflict_to_dict(c))
    return conflicts


def _emso_conflicts_for_picture() -> list[dict[str, Any]]:
    if _bus_subscriber and _bus_subscriber.emso_conflicts():
        return _bus_subscriber.emso_conflicts()
    return _fixture_emso_conflicts()


def _commlink_state() -> tuple[dict[str, object], dict[str, object]]:
    if _bus_subscriber and _bus_subscriber.connected:
        return _bus_subscriber.commlink_statuses(), _bus_subscriber.commlink_reservations()
    with _lock:
        return dict(_commlink_statuses), dict(_commlink_reservations)


def _seed_commlink_statuses() -> None:
    directory = _load_directory()
    for link in directory.comm_links:
        from uci_common.commlink_messages import CommLinkStatusReport

        _commlink_statuses[link.id] = CommLinkStatusReport(
            message_id="",
            link_id=link.id,
            resource_id=link.resource_id or "",
            status="active",
            billing_model="flat_rate",
            billing_label="Active",
            reservation_status="none",
            used_minutes=0,
            estimated_cost=0.0,
            currency="USD",
        )


def _build_picture() -> dict[str, Any]:
    with _lock:
        highlight = _highlight_entity_id
        geo = _geo_filter

    if _harness_mode:
        picture = build_harness_picture(geo_filter=geo, highlight_entity_id=highlight)
        return picture

    directory = _load_directory()
    statuses, reservations = _commlink_state()
    display = build_commlink_display(directory, statuses, reservations)
    snap = _engine.snapshot() if _engine is not None else None
    sim_minutes = float(getattr(snap, "sim_minutes", 0.0) if snap else 0.0)
    scenario = getattr(_engine, "_scenario", None) if _engine is not None else None
    spectrum_analytics = _bus_subscriber.spectrum_analytics() if _bus_subscriber else None
    picture = build_rf_picture(
        sim_minutes=sim_minutes,
        commlink_display=display,
        directory_links=directory.comm_links,
        engine_snapshot=snap,
        scenario=scenario,
        emso_conflicts=_emso_conflicts_for_picture(),
        spectrum_analytics=spectrum_analytics,
        highlight_entity_id=highlight,
        bus_connected=bool(_bus_subscriber and _bus_subscriber.connected),
    )
    assert_rf_picture_contract(picture)
    return apply_geo_filter(picture, geo)


def _refresh_picture() -> dict[str, Any]:
    global _picture_cache
    picture = _build_picture()
    with _lock:
        _picture_cache = picture
    return dict(picture)


def _start_bus() -> None:
    global _bus, _bus_subscriber
    if _REDIS_URL.startswith("memory://"):
        logger.info("REDIS_URL=memory:// — embedded commlink fixtures only")
        return
    try:
        _bus = RedisBus(redis_url=_REDIS_URL)
        _bus_subscriber = RfBusSubscriber(_bus, on_refresh=_refresh_picture)
        _bus_subscriber.start()
    except Exception:
        logger.exception("Redis bus unavailable — using embedded mode")


@app.on_event("startup")
def _startup() -> None:
    _load_directory()
    _seed_commlink_statuses()
    _start_bus()
    _refresh_picture()


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "rf-display",
        "harness_mode": _harness_mode,
        "bus_connected": bool(_bus_subscriber and _bus_subscriber.connected),
        "redis_url": _REDIS_URL.split("@")[-1] if "@" in _REDIS_URL else _REDIS_URL,
    }


@app.get("/api/picture")
def get_picture() -> dict[str, Any]:
    with _lock:
        if not _picture_cache:
            return _refresh_picture()
        return dict(_picture_cache)


@app.get("/api/stream")
def stream_picture() -> StreamingResponse:
    def _gen():
        last = ""
        while True:
            payload = _refresh_picture()
            body = json.dumps(payload, default=str)
            if body != last:
                yield f"data: {body}\n\n"
                last = body
            time.sleep(1.0)

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.get("/api/highlight")
def get_highlight() -> dict[str, str | None]:
    with _lock:
        return {"entity_id": _highlight_entity_id}


@app.post("/api/highlight")
def set_highlight(body: HighlightBody) -> dict[str, str]:
    global _highlight_entity_id
    with _lock:
        _highlight_entity_id = body.entity_id or None
    _refresh_picture()
    return {"entity_id": _highlight_entity_id or ""}


@app.delete("/api/highlight")
def clear_highlight() -> dict[str, str]:
    global _highlight_entity_id
    with _lock:
        _highlight_entity_id = None
    _refresh_picture()
    return {"entity_id": ""}


@app.get("/api/geo-filter")
def get_geo_filter() -> dict[str, Any]:
    with _lock:
        return {"geo_filter": _geo_filter}


@app.post("/api/geo-filter")
def set_geo_filter(body: GeoFilterBody) -> dict[str, Any]:
    global _geo_filter
    payload = body.model_dump()
    errors = validate_geo_filter(payload)
    if errors:
        return {"status": "error", "errors": errors}
    with _lock:
        _geo_filter = payload
    picture = _refresh_picture()
    return {"status": "ok", "geo_filter": _geo_filter, "geo_filter_summary": picture.get("geo_filter_summary")}


@app.delete("/api/geo-filter")
def clear_geo_filter() -> dict[str, Any]:
    global _geo_filter
    with _lock:
        _geo_filter = None
    picture = _refresh_picture()
    return {"status": "ok", "geo_filter": None, "geo_filter_summary": picture.get("geo_filter_summary")}


@app.get("/api/harness/verify")
def harness_verify() -> dict[str, Any]:
    picture = _build_picture()
    results = verify_rf_features(picture)
    passed = all(r["passed"] for r in results)
    return {"passed": passed, "harness_mode": _harness_mode, "checks": results}


@app.post("/api/commlink/status")
async def ingest_status(body: bytes) -> dict[str, str]:
    report = parse_status_report_xml(body.decode("utf-8"))
    with _lock:
        _commlink_statuses[report.link_id] = report
    _refresh_picture()
    return {"status": "ok"}


@app.post("/api/commlink/reservation")
async def ingest_reservation(body: bytes) -> dict[str, str]:
    report = parse_reservation_report_xml(body.decode("utf-8"))
    with _lock:
        _commlink_reservations[report.reservation_id] = report
        if _emso_engine is not None:
            _emso_engine.ingest_reservation_report(report)
    _refresh_picture()
    return {"status": "ok"}
