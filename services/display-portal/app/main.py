"""Central operator portal — display and OMS monitoring status."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from display_landing import collect_portal_status, render_landing_html

app = FastAPI(title="OMS Display Portal", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "display-portal"}


@app.get("/api/portal/status")
def portal_status() -> dict:
    return collect_portal_status()


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return render_landing_html(collect_portal_status(), title="OMS Operator Portal")


@app.get("/landing", response_class=HTMLResponse)
def landing() -> str:
    return root()
