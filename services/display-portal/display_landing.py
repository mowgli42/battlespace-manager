"""Operator landing page: probe OMS monitoring and display service ports."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

_DEFAULT_PUBLIC_HOST = "localhost"


def _public_host() -> str:
    return os.getenv("DISPLAY_PUBLIC_HOST", _DEFAULT_PUBLIC_HOST).strip() or _DEFAULT_PUBLIC_HOST


def _env_url(key: str, default: str) -> str:
    val = os.getenv(key, default).strip()
    if val.lower() in ("none", "off", "0", "false"):
        return ""
    return val.rstrip("/")


def load_display_registry() -> list[dict[str, Any]]:
    """Registered operator displays (UI + API)."""
    host = _public_host()
    return [
        {
            "id": "entity",
            "label": "Entity Display",
            "description": "ADS-B tracks, commlink overlays, affiliation filters",
            "ui_port": int(os.getenv("ENTITY_UI_PORT", "8080")),
            "api_port": int(os.getenv("ENTITY_API_PORT", "8003")),
            "ui_url": _env_url("ENTITY_UI_URL", f"http://{host}:8080"),
            "api_url": _env_url("ENTITY_API_URL", f"http://{host}:8003"),
            "ui_probe_url": _env_url("ENTITY_UI_PROBE_URL", os.getenv("ENTITY_UI_URL", f"http://{host}:8080")),
            "api_probe_url": _env_url("ENTITY_API_PROBE_URL", os.getenv("ENTITY_API_URL", f"http://{host}:8003")),
            "spa_path": "/",
            "docs_path": "/docs",
        },
        {
            "id": "battlespace",
            "label": "Battlespace Display",
            "description": "F2T2EA kill chain, tasking, OMS AI recommendations",
            "ui_port": int(os.getenv("BATTLESPACE_UI_PORT", "8081")),
            "api_port": int(os.getenv("BATTLESPACE_API_PORT", "8004")),
            "ui_url": _env_url("BATTLESPACE_UI_URL", f"http://{host}:8081"),
            "api_url": _env_url("BATTLESPACE_API_URL", f"http://{host}:8004"),
            "ui_probe_url": _env_url(
                "BATTLESPACE_UI_PROBE_URL", os.getenv("BATTLESPACE_UI_URL", f"http://{host}:8081")
            ),
            "api_probe_url": _env_url(
                "BATTLESPACE_API_PROBE_URL", os.getenv("BATTLESPACE_API_URL", f"http://{host}:8004")
            ),
            "spa_path": "/",
            "docs_path": "/docs",
        },
        {
            "id": "rf",
            "label": "RF Display",
            "description": "RF spectrum, EMSO deconfliction, JRFL corridors",
            "ui_port": int(os.getenv("RF_UI_PORT", "8082")),
            "api_port": int(os.getenv("RF_API_PORT", "8005")),
            "ui_url": _env_url("RF_UI_URL", f"http://{host}:8082"),
            "api_url": _env_url("RF_API_URL", f"http://{host}:8005"),
            "ui_probe_url": _env_url("RF_UI_PROBE_URL", os.getenv("RF_UI_URL", f"http://{host}:8082")),
            "api_probe_url": _env_url("RF_API_PROBE_URL", os.getenv("RF_API_URL", f"http://{host}:8005")),
            "spa_path": "/",
            "docs_path": "/docs",
        },
    ]


def load_monitoring_registry() -> list[dict[str, Any]]:
    """OMS Prometheus / Grafana endpoints (o-my monitoring profile)."""
    host = _public_host()
    return [
        {
            "id": "prometheus",
            "label": "Prometheus",
            "description": "o-my metrics scrape target (:9090)",
            "port": int(os.getenv("PROMETHEUS_PORT", "9090")),
            "url": _env_url("PROMETHEUS_URL", f"http://{host}:9090"),
            "probe_url": _env_url("PROMETHEUS_PROBE_URL", os.getenv("PROMETHEUS_URL", f"http://{host}:9090")),
            "health_path": "/-/healthy",
            "link_path": "/",
        },
        {
            "id": "grafana",
            "label": "Grafana",
            "description": "o-my UCI dashboards (:3000, admin/admin)",
            "port": int(os.getenv("GRAFANA_PORT", "3000")),
            "url": _env_url("GRAFANA_URL", f"http://{host}:3000"),
            "probe_url": _env_url("GRAFANA_PROBE_URL", os.getenv("GRAFANA_URL", f"http://{host}:3000")),
            "health_path": "/api/health",
            "link_path": "/",
        },
    ]


def _http_probe(
    base_url: str,
    path: str = "/",
    *,
    timeout: float = 1.5,
    accept_json: bool = False,
) -> dict[str, Any]:
    if not base_url:
        return {"status": "unconfigured", "detail": "URL not configured", "http_status": None}
    url = f"{base_url.rstrip('/')}{path}"
    started = time.time()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.status
            body = resp.read(4096).decode("utf-8", errors="replace")
            latency_ms = int((time.time() - started) * 1000)
            if code >= 400:
                return {"status": "offline", "detail": f"HTTP {code}", "http_status": code, "latency_ms": latency_ms}
            detail = f"HTTP {code}"
            if accept_json and body.strip().startswith("{"):
                try:
                    data = json.loads(body)
                    if isinstance(data, dict):
                        svc = data.get("service") or data.get("status")
                        if svc:
                            detail = str(svc)
                        if data.get("status") in ("degraded",):
                            return {
                                "status": "degraded",
                                "detail": detail,
                                "http_status": code,
                                "latency_ms": latency_ms,
                            }
                except json.JSONDecodeError:
                    pass
            return {"status": "live", "detail": detail, "http_status": code, "latency_ms": latency_ms}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "status": "offline",
            "detail": str(exc),
            "http_status": None,
            "latency_ms": int((time.time() - started) * 1000),
        }


def collect_portal_status(*, current_display: str | None = None) -> dict[str, Any]:
    """Probe monitoring stack and all display UI/API ports."""
    displays: list[dict[str, Any]] = []
    for spec in load_display_registry():
        ui = _http_probe(spec["ui_probe_url"], "/")
        api = _http_probe(spec["api_probe_url"], "/health", accept_json=True)
        overall = "live" if ui["status"] == "live" and api["status"] == "live" else (
            "degraded" if ui["status"] == "live" or api["status"] == "live" else "offline"
        )
        displays.append(
            {
                **spec,
                "status": overall,
                "ui_status": ui,
                "api_status": api,
                "is_current": spec["id"] == current_display,
            }
        )

    monitoring: list[dict[str, Any]] = []
    for spec in load_monitoring_registry():
        probe = _http_probe(spec["probe_url"], spec["health_path"], accept_json=spec["id"] == "grafana")
        monitoring.append({**spec, "status": probe["status"], "probe": probe})

    live_displays = sum(1 for d in displays if d["status"] == "live")
    live_monitoring = sum(1 for m in monitoring if m["status"] == "live")

    return {
        "generated_ms": int(time.time() * 1000),
        "current_display": current_display,
        "public_host": _public_host(),
        "displays": displays,
        "monitoring": monitoring,
        "summary": {
            "displays_live": live_displays,
            "displays_total": len(displays),
            "monitoring_live": live_monitoring,
            "monitoring_total": len(monitoring),
        },
    }


def _status_class(status: str) -> str:
    if status == "live":
        return "live"
    if status == "degraded":
        return "degraded"
    if status == "unconfigured":
        return "unconfigured"
    return "offline"


def _status_label(status: str) -> str:
    return {
        "live": "Live",
        "degraded": "Degraded",
        "offline": "Offline",
        "unconfigured": "Unconfigured",
    }.get(status, status.title())


def render_landing_html(status: dict[str, Any], *, title: str = "OMS Operator Displays") -> str:
    """Render operator landing page HTML."""
    current = status.get("current_display")
    summary = status.get("summary") or {}
    displays = status.get("displays") or []
    monitoring = status.get("monitoring") or []

    def row_endpoints(d: dict[str, Any]) -> str:
        ui = d.get("ui_status") or {}
        api = d.get("api_status") or {}
        current_cls = " current" if d.get("is_current") else ""
        return f"""
        <article class="card{current_cls}">
          <header>
            <span class="dot {_status_class(d.get('status', 'offline'))}"></span>
            <h3>{d.get('label', '')}</h3>
            <span class="pill {_status_class(d.get('status', 'offline'))}">{_status_label(d.get('status', 'offline'))}</span>
          </header>
          <p class="desc">{d.get('description', '')}</p>
          <div class="ports">
            <div class="port">
              <span class="port-label">UI :{d.get('ui_port')}</span>
              <span class="port-status {_status_class(ui.get('status', 'offline'))}">{_status_label(ui.get('status', 'offline'))}</span>
              <a href="{d.get('ui_url', '#')}{d.get('spa_path', '/')}" class="link">Open UI</a>
            </div>
            <div class="port">
              <span class="port-label">API :{d.get('api_port')}</span>
              <span class="port-status {_status_class(api.get('status', 'offline'))}">{_status_label(api.get('status', 'offline'))}</span>
              <a href="{d.get('api_url', '#')}{d.get('docs_path', '/docs')}" class="link">API docs</a>
            </div>
          </div>
        </article>"""

    def mon_row(m: dict[str, Any]) -> str:
        probe = m.get("probe") or {}
        return f"""
        <article class="card compact">
          <header>
            <span class="dot {_status_class(m.get('status', 'offline'))}"></span>
            <h3>{m.get('label', '')}</h3>
            <span class="pill {_status_class(m.get('status', 'offline'))}">{_status_label(m.get('status', 'offline'))}</span>
          </header>
          <p class="desc">{m.get('description', '')}</p>
          <p class="meta">:{m.get('port')} · {probe.get('detail', '')}</p>
          <a href="{m.get('url', '#')}{m.get('link_path', '/')}" class="link">Open {m.get('label', '')}</a>
        </article>"""

    current_banner = ""
    if current:
        label = next((d["label"] for d in displays if d["id"] == current), current)
        current_banner = f'<p class="you-are-here">You reached this page from <strong>{label}</strong>.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <title>{title}</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: rgba(18, 24, 42, 0.92);
      --border: rgba(100, 116, 139, 0.35);
      --text: #e2e8f0;
      --muted: #94a3b8;
      --live: #34d399;
      --degraded: #fbbf24;
      --offline: #64748b;
      --accent: #60a5fa;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, sans-serif;
      background: radial-gradient(ellipse at top, #141b33 0%, var(--bg) 55%);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.45;
    }}
    .wrap {{ max-width: 56rem; margin: 0 auto; padding: 2rem 1.25rem 3rem; }}
    h1 {{ margin: 0 0 0.35rem; font-size: 1.6rem; letter-spacing: -0.02em; }}
    .lede {{ color: var(--muted); margin: 0 0 1.5rem; max-width: 42rem; }}
    .summary {{
      display: flex; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 1.75rem;
    }}
    .stat {{
      background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
      padding: 0.65rem 0.9rem; min-width: 9rem;
    }}
    .stat strong {{ display: block; font-size: 1.25rem; }}
    .stat span {{ color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; }}
    h2 {{
      font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em;
      color: #a5b4fc; margin: 0 0 0.75rem;
    }}
    .grid {{ display: grid; gap: 0.85rem; margin-bottom: 2rem; }}
    @media (min-width: 720px) {{ .grid.displays {{ grid-template-columns: 1fr 1fr; }} }}
    .card {{
      background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
      padding: 1rem 1.1rem;
    }}
    .card.current {{ border-color: rgba(96, 165, 250, 0.55); box-shadow: 0 0 0 1px rgba(96,165,250,0.15); }}
    .card header {{ display: flex; align-items: center; gap: 0.55rem; margin-bottom: 0.45rem; }}
    .card h3 {{ margin: 0; font-size: 1rem; flex: 1; }}
    .dot {{ width: 9px; height: 9px; border-radius: 50%; background: var(--offline); flex-shrink: 0; }}
    .dot.live {{ background: var(--live); }}
    .dot.degraded {{ background: var(--degraded); }}
    .pill {{
      font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.06em;
      padding: 0.15rem 0.45rem; border-radius: 999px; background: rgba(100,116,139,0.25); color: var(--muted);
    }}
    .pill.live {{ background: rgba(52,211,153,0.18); color: #6ee7b7; }}
    .pill.degraded {{ background: rgba(251,191,36,0.18); color: #fcd34d; }}
    .desc {{ margin: 0 0 0.75rem; color: var(--muted); font-size: 0.88rem; }}
    .ports {{ display: grid; gap: 0.5rem; }}
    .port {{
      display: grid; grid-template-columns: 1fr auto; gap: 0.35rem 0.75rem; align-items: center;
      padding: 0.45rem 0.55rem; border-radius: 8px; background: rgba(0,0,0,0.22);
      font-size: 0.82rem;
    }}
    .port-label {{ font-family: ui-monospace, monospace; color: #c4b5fd; }}
    .port-status {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .port-status.live {{ color: var(--live); }}
    .port-status.degraded {{ color: var(--degraded); }}
    .port-status.offline {{ color: var(--offline); }}
    .link {{ grid-column: 1 / -1; color: var(--accent); text-decoration: none; font-size: 0.82rem; }}
    .link:hover {{ text-decoration: underline; }}
    .meta {{ margin: 0.35rem 0 0.5rem; color: var(--muted); font-size: 0.78rem; font-family: ui-monospace, monospace; }}
    .you-are-here {{ margin: 0 0 1rem; padding: 0.55rem 0.75rem; border-radius: 8px; background: rgba(96,165,250,0.12); border: 1px solid rgba(96,165,250,0.25); font-size: 0.88rem; }}
    footer {{ color: var(--muted); font-size: 0.75rem; margin-top: 1.5rem; }}
    code {{ font-family: ui-monospace, monospace; font-size: 0.85em; }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>{title}</h1>
    <p class="lede">Service status for OMS operator displays and monitoring. Page auto-refreshes every 30 seconds.</p>
    {current_banner}
    <div class="summary">
      <div class="stat"><strong>{summary.get('displays_live', 0)}/{summary.get('displays_total', 0)}</strong><span>Displays live</span></div>
      <div class="stat"><strong>{summary.get('monitoring_live', 0)}/{summary.get('monitoring_total', 0)}</strong><span>Monitoring live</span></div>
    </div>

    <h2>Operator displays</h2>
    <div class="grid displays">{''.join(row_endpoints(d) for d in displays)}</div>

    <h2>OMS monitoring</h2>
    <p class="lede" style="margin-top:-0.5rem;margin-bottom:0.85rem;">Start o-my with <code>docker compose --profile monitoring up</code> for Prometheus (:9090) and Grafana (:3000).</p>
    <div class="grid">{''.join(mon_row(m) for m in monitoring)}</div>

    <footer>
      <a href="/api/portal/status" style="color:var(--accent)">JSON status</a>
      · generated {status.get('generated_ms', '')}
    </footer>
  </div>
</body>
</html>"""
