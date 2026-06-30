#!/usr/bin/env python3
"""Screenshot CAOC tasking queue at T+0 — verifies OMS platforms + ATO tasks render."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8081"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/images/tasking-queue-t0-fix.png")


def api_base(ui: str) -> str:
    for ui_port, api_port in (("8081", "8004"), ("5173", "8004")):
        if f":{ui_port}" in ui:
            return ui.replace(f":{ui_port}", f":{api_port}")
    return "http://127.0.0.1:8004"


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && python3 -m playwright install chromium", file=sys.stderr)
        sys.exit(1)

    api = api_base(BASE)
    OUT.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        page.reload(wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        page.locator("nav.tabs button").filter(has_text=re.compile("Decisions", re.I)).first.click()
        page.wait_for_function(
            """() => {
              const el = document.querySelector('.queue-meta');
              if (!el) return false;
              const m = el.textContent.match(/(\\d+) tasks/);
              return m && parseInt(m[1], 10) > 0;
            }""",
            timeout=45000,
        )
        page.wait_for_timeout(800)
        panel = page.locator(".tasking-panel")
        panel.wait_for(state="visible", timeout=10000)
        panel.screenshot(path=str(OUT))
        pic = page.request.get(f"{api}/api/picture").json()
        n_platforms = len(pic.get("platforms") or [])
        n_tasks = len(pic.get("task_rows") or [])
        browser.close()

    print(f"OK: {n_platforms} platforms, {n_tasks} tasks → {OUT}")


if __name__ == "__main__":
    main()
