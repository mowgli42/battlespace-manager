"""Register operator portal routes on a display API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.responses import HTMLResponse

try:
    from app.display_landing import collect_portal_status, render_landing_html
except ImportError:
    from display_landing import collect_portal_status, render_landing_html

if TYPE_CHECKING:
    from fastapi import FastAPI


def register_portal_routes(app: FastAPI, *, display_id: str, title: str) -> None:
    @app.get("/api/portal/status")
    def portal_status() -> dict:
        return collect_portal_status(current_display=display_id)

    @app.get("/landing", response_class=HTMLResponse)
    def landing_page() -> str:
        return render_landing_html(collect_portal_status(current_display=display_id), title=title)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def portal_root() -> str:
        return landing_page()
