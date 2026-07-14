#!/usr/bin/env python3
"""Capture battlespace-manager screenshots for route-threat / popup-tasker slice.

Expects harness API on :8004 and UI on :8081 (or pass UI base URL as argv[1]).
Writes under docs/images/presentation/metrics and docs/images/walkthrough.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images"
METRICS = IMG / "presentation" / "metrics"
WALK = IMG / "walkthrough"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8081"


def api_base(ui: str) -> str:
    for ui_port, api_port in (("8081", "8004"), ("5173", "8004")):
        if f":{ui_port}" in ui:
            return ui.replace(f":{ui_port}", f":{api_port}")
    return "http://127.0.0.1:8004"


def click_tab(page, label: str) -> None:
    page.locator("nav.tabs button").filter(has_text=re.compile(label, re.I)).first.click()


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && python3 -m playwright install chromium", file=sys.stderr)
        sys.exit(1)

    api = api_base(BASE)
    METRICS.mkdir(parents=True, exist_ok=True)
    WALK.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        page.reload(wait_until="domcontentloaded", timeout=60000)
        page.wait_for_function(
            """() => {
              const el = document.querySelector('.attention-rail ul');
              return el && el.querySelectorAll('li button').length > 0;
            }""",
            timeout=45000,
        )
        page.wait_for_timeout(600)

        pic = page.request.get(f"{api}/api/picture").json()
        n_routes = len(pic.get("route_threats") or [])
        n_popup = sum(1 for a in (pic.get("attention_queue") or []) if a.get("kind") == "POPUP")
        n_tasks = len(pic.get("task_rows") or [])
        print(f"picture: route_threats={n_routes} popup_attention={n_popup} tasks={n_tasks}")

        # Attention rail with POPUP + TST
        page.locator(".attention-rail").screenshot(path=str(METRICS / "metric-attention-rail.png"))
        (METRICS / "metric-attention-rail.txt").write_text(
            "Attention rail — POPUP route threats + TST queue (uci.threat.notification / harness)\n",
            encoding="utf-8",
        )
        page.screenshot(path=str(WALK / "08-attention-popup-route.png"))

        # Routes tab — impacted routes list
        click_tab(page, "Routes")
        page.wait_for_selector(".route-threat-panel table tbody tr", timeout=15000)
        page.wait_for_timeout(400)
        page.locator(".route-threat-panel").screenshot(path=str(METRICS / "metric-route-threats.png"))
        (METRICS / "metric-route-threats.txt").write_text(
            "Impacted routes — closest-first list with Strike/EJ/Jam bands (picture.route_threats)\n",
            encoding="utf-8",
        )
        page.screenshot(path=str(WALK / "08-routes-impacted.png"))

        # Decisions — popup banded tasks (All filter so Strike/EJ/Jam rows show)
        click_tab(page, "Decisions")
        page.wait_for_selector(".tasking-panel .queue-meta", timeout=15000)
        page.locator("button.filter-chip").filter(has_text=re.compile(r"^All", re.I)).first.click()
        page.wait_for_timeout(500)
        page.locator(".tasking-panel").screenshot(path=str(WALK / "08-tasking-popup-bands.png"))
        page.screenshot(path=str(IMG / "gulfwar-tasking.png"))

        # Map overview with harness narrative
        click_tab(page, "Battlespace")
        page.wait_for_timeout(800)
        page.screenshot(path=str(WALK / "08-battlespace-popup-threat.png"))
        page.screenshot(path=str(IMG / "gulfwar-map.png"))

        browser.close()

    print(f"OK → {METRICS}/metric-attention-rail.png, metric-route-threats.png")
    print(f"OK → {WALK}/08-*.png")


if __name__ == "__main__":
    main()
