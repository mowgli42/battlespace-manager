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

from app.rf_picture_contract import assert_rf_picture_contract, build_rf_picture
from uci_common import (
    build_commlink_display,
    parse_directory_xml,
    parse_reservation_report_xml,
    parse_status_report_xml,
)
from uci_common.emso_deconfliction import EmsoDeconflictionEngine
from uci_common.emso_messages import EmsoConflictReport

if TYPE_CHECKING:
    from uci_common.gulfwar_engine import GulfWarEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rf-display-api")

app = FastAPI(title="RF Display API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_XML = _REPO_ROOT / "fixtures" / "commlink-directory-v1.1.xml"
_xml_path = Path(os.getenv("COMMLINK_DIRECTORY_XML", str(_DEFAULT_XML)))

_engine: GulfWarEngine | None = None
_lock = threading.Lock()
_commlink_statuses: dict[str, object] = {}
_commlink_reservations: dict[str, object] = {}
_directory = None
_emso_engine: EmsoDeconflictionEngine | None = None
_picture_cache: dict[str, Any] = {}


def _load_directory():
    global _directory, _emso_engine
    if _directory is not None:
        return _directory
    if not _xml_path.is_file():
        raise FileNotFoundError(f"Directory XML not found: {_xml_path}")
    _directory = parse_directory_xml(_xml_path.read_text(encoding="utf-8"))
    _emso_engine = EmsoDeconflictionEngine(document=_directory)
    logger.info("Loaded commlink directory v%s (%d links)", _directory.version, len(_directory.comm_links))
    return _directory


def set_engine(engine: GulfWarEngine) -> None:
    global _engine
    _engine = engine


def _emso_conflict_dicts() -> list[dict[str, Any]]:
    directory = _load_directory()
    engine = EmsoDeconflictionEngine(document=directory)
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


def _conflict_to_dict(report: EmsoConflictReport) -> dict[str, Any]:
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
    directory = _load_directory()
    display = build_commlink_display(directory, _commlink_statuses, _commlink_reservations)
    snap = _engine.snapshot() if _engine is not None else None
    sim_minutes = float(getattr(snap, "sim_minutes", 0.0) if snap else 0.0)
    scenario = getattr(_engine, "_scenario", None) if _engine is not None else None
    picture = build_rf_picture(
        sim_minutes=sim_minutes,
        commlink_display=display,
        directory_links=directory.comm_links,
        engine_snapshot=snap,
        scenario=scenario,
        emso_conflicts=_emso_conflict_dicts(),
    )
    assert_rf_picture_contract(picture)
    return picture


def _refresh_picture() -> dict[str, Any]:
    global _picture_cache
    with _lock:
        _picture_cache = _build_picture()
        return dict(_picture_cache)


@app.on_event("startup")
def _startup() -> None:
    _load_directory()
    _seed_commlink_statuses()
    _refresh_picture()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "rf-display"}


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
