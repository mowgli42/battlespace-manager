"""OMS AI recommendation service registry, health probes, and picture merge."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

# Registered OMS services that may produce recommendations for the operator picture.
_DEFAULT_REGISTRY: list[dict[str, Any]] = [
    {
        "service_id": "mission-advisor",
        "label": "Mission Advisor",
        "description": "Rule/LLM strike and SEAD suggestions; ISR auto-task on bus",
        "env_url": "ADVISOR_URL",
        "default_url": "http://127.0.0.1:8005",
        "health_path": "/health",
        "snapshot_path": "/api/advisor/snapshot",
        "scopes": ["targets", "tasks"],
        "bus_topics": ["uci.agent.suggestion", "uci.task"],
        "recommendation_kinds": ["strike_suggestion", "isr_assignment"],
    },
    {
        "service_id": "entity-sorter",
        "label": "Entity Sorter",
        "description": "Entity classification and threat tagging (o-my pipeline)",
        "env_url": "ENTITY_SORTER_URL",
        "default_url": "http://127.0.0.1:8002",
        "health_path": "/health",
        "snapshot_path": "",
        "scopes": ["entities"],
        "bus_topics": ["uci.entity.notification"],
        "recommendation_kinds": ["entity_classification"],
    },
    {
        "service_id": "task-allocator",
        "label": "Task Allocator",
        "description": "Platform assignment and task lifecycle recommendations",
        "env_url": "TASK_ALLOCATOR_URL",
        "default_url": "http://127.0.0.1:8018",
        "health_path": "/health",
        "snapshot_path": "",
        "scopes": ["tasks", "platforms"],
        "bus_topics": ["uci.task", "uci.task.status"],
        "recommendation_kinds": ["task_assignment"],
    },
]

_EMBEDDED_SERVICE_ID = "embedded-advisor"


def _service_url(spec: dict[str, Any]) -> str:
    env_key = str(spec.get("env_url", "")).strip()
    val = os.getenv(env_key, "").strip() if env_key else ""
    if val.lower() in ("none", "off", "0", "false"):
        return ""
    if val:
        return val.rstrip("/")
    return (spec.get("default_url") or "").strip().rstrip("/")


def load_service_registry() -> list[dict[str, Any]]:
    raw = os.getenv("OMS_AI_SERVICES_JSON", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    return list(_DEFAULT_REGISTRY)


def _http_get_json(url: str, *, timeout: float = 1.5) -> dict[str, Any]:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def offline_service_row(spec: dict[str, Any], *, detail: str = "Harness mode — not probed") -> dict[str, Any]:
    """Build a deterministic offline status row without network I/O."""
    service_id = spec.get("service_id", "")
    return {
        "service_id": service_id,
        "label": spec.get("label", service_id),
        "description": spec.get("description", ""),
        "url": _service_url(spec) or None,
        "scopes": list(spec.get("scopes") or []),
        "bus_topics": list(spec.get("bus_topics") or []),
        "recommendation_kinds": list(spec.get("recommendation_kinds") or []),
        "status": "offline",
        "recommendation_count": 0,
        "isr_assignment_count": 0,
        "open_recommendation_count": 0,
        "last_probe_ms": int(time.time() * 1000),
        "detail": detail,
    }


def build_offline_registry_rows(*, detail: str = "Harness mode — not probed") -> list[dict[str, Any]]:
    return [offline_service_row(spec, detail=detail) for spec in load_service_registry()]


def probe_service(spec: dict[str, Any], *, now: float | None = None) -> dict[str, Any]:
    """Probe one OMS service; return status row for operator picture."""
    now = now if now is not None else time.time()
    service_id = spec.get("service_id", "")
    url = _service_url(spec)
    base = {
        "service_id": service_id,
        "label": spec.get("label", service_id),
        "description": spec.get("description", ""),
        "url": url or None,
        "scopes": list(spec.get("scopes") or []),
        "bus_topics": list(spec.get("bus_topics") or []),
        "recommendation_kinds": list(spec.get("recommendation_kinds") or []),
        "status": "unconfigured",
        "recommendation_count": 0,
        "isr_assignment_count": 0,
        "open_recommendation_count": 0,
        "last_probe_ms": int(now * 1000),
        "detail": "",
    }
    if not url:
        base["detail"] = "No service URL configured"
        return base

    health_path = spec.get("health_path") or "/health"
    try:
        health = _http_get_json(f"{url}{health_path}")
        base["status"] = "live" if health.get("status") in ("ok", "healthy") else "degraded"
        base["detail"] = str(health.get("service") or health.get("status") or "ok")
        base["service_health"] = health
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        base["status"] = "offline"
        base["detail"] = str(exc)
        return base

    snapshot_path = (spec.get("snapshot_path") or "").strip()
    if snapshot_path and service_id == "mission-advisor":
        try:
            snap = _http_get_json(f"{url}{snapshot_path}")
            suggestions = list(snap.get("suggestions") or [])
            isr = list(snap.get("isr_assignments") or [])
            open_sugs = [s for s in suggestions if s.get("status") not in ("accepted", "dismissed")]
            base["recommendation_count"] = len(suggestions)
            base["isr_assignment_count"] = len(isr)
            base["open_recommendation_count"] = len(open_sugs)
            base["snapshot"] = {
                "sim_minutes": snap.get("sim_minutes"),
                "suggestion_count": len(suggestions),
                "isr_count": len(isr),
            }
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            base["status"] = "degraded"
            base["detail"] = f"health ok; snapshot failed: {exc}"
    return base


def _embedded_enabled() -> bool:
    return os.getenv("ADVISOR_EMBEDDED", "0").lower() in ("1", "true", "yes")


def _embedded_service_row(*, recommendation_count: int = 0, isr_count: int = 0) -> dict[str, Any]:
    return {
        "service_id": _EMBEDDED_SERVICE_ID,
        "label": "Embedded Advisor (dev)",
        "description": "In-process rule engine — not an OMS microservice",
        "url": None,
        "scopes": ["targets", "tasks"],
        "bus_topics": ["uci.agent.suggestion", "uci.task"],
        "recommendation_kinds": ["strike_suggestion", "isr_assignment"],
        "status": "live",
        "recommendation_count": recommendation_count,
        "isr_assignment_count": isr_count,
        "open_recommendation_count": recommendation_count,
        "last_probe_ms": int(time.time() * 1000),
        "detail": "ADVISOR_EMBEDDED=1",
    }


def refresh_oms_ai_services(
    engine_snapshot: Any | None = None,
    *,
    dedup_keys: set[str] | None = None,
    open_suggestions: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """
    Probe OMS AI services and collect recommendations only from live services.

    Returns (service_rows, suggestions, isr_assignments, summary).
    """
    registry = load_service_registry()
    service_rows = [probe_service(spec) for spec in registry]

    suggestions: list[dict[str, Any]] = []
    isr_assignments: list[dict[str, Any]] = []
    dedup_keys = dedup_keys or set()

    live_advisor = next(
        (s for s in service_rows if s["service_id"] == "mission-advisor" and s["status"] == "live"),
        None,
    )
    if live_advisor and live_advisor.get("url"):
        try:
            snap = _http_get_json(f"{live_advisor['url']}/api/advisor/snapshot")
            suggestions = list(snap.get("suggestions") or [])
            isr_assignments = list(snap.get("isr_assignments") or [])
            for sug in suggestions:
                sug.setdefault("source_service", "mission-advisor")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            live_advisor["status"] = "degraded"
            live_advisor["detail"] = "snapshot unavailable"

    elif _embedded_enabled() and engine_snapshot is not None:
        from uci_common.advisor_bridge import run_embedded_evaluation

        embedded_sugs, embedded_isr, dedup_keys = run_embedded_evaluation(
            engine_snapshot,
            dedup_keys=dedup_keys,
            publish=None,
            auto_isr=True,
            suggest_strike=True,
        )
        for sug in embedded_sugs:
            sug["source_service"] = _EMBEDDED_SERVICE_ID
        suggestions = embedded_sugs
        isr_assignments = embedded_isr
        service_rows.append(
            _embedded_service_row(
                recommendation_count=len([s for s in suggestions if s.get("status") != "accepted"]),
                isr_count=len(isr_assignments),
            )
        )

    # Preserve operator dismiss/snooze/accept state from display API when provided.
    if open_suggestions is not None and suggestions:
        by_id = {s.get("suggestion_id"): s for s in open_suggestions}
        merged: list[dict[str, Any]] = []
        for sug in suggestions:
            sid = sug.get("suggestion_id")
            if sid and sid in by_id:
                merged.append({**sug, **{k: v for k, v in by_id[sid].items() if k in ("status", "accepted_task_id", "snooze_until_sim")}})
            else:
                merged.append(sug)
        suggestions = merged

    live_services = [s for s in service_rows if s["status"] == "live"]
    open_recs = [s for s in suggestions if s.get("status") not in ("accepted", "dismissed")]
    summary = {
        "live_count": len(live_services),
        "total_services": len(service_rows),
        "offline_count": sum(1 for s in service_rows if s["status"] == "offline"),
        "unconfigured_count": sum(1 for s in service_rows if s["status"] == "unconfigured"),
        "open_recommendations": len(open_recs),
        "isr_assignments": len(isr_assignments),
        "any_live": len(live_services) > 0,
    }
    return service_rows, suggestions, isr_assignments, summary


def merge_oms_attention(
    attention_queue: list[dict[str, Any]],
    suggestions: list[dict[str, Any]],
    *,
    services_live: bool,
) -> list[dict[str, Any]]:
    if not services_live or not suggestions:
        return list(attention_queue)
    from uci_common.advisor_bridge import merge_advisor_attention

    return merge_advisor_attention(attention_queue, suggestions)
