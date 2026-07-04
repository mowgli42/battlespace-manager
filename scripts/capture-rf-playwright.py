#!/usr/bin/env python3
"""Capture RF display walkthrough screenshots (Playwright)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images" / "rf-walkthrough"


def wait_url(url: str, timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=3) as resp:
                if resp.status < 400:
                    return
        except Exception:
            time.sleep(1)
    raise TimeoutError(f"URL not ready: {url}")


def snap(page, url: str, out: Path, wait_ms: int = 6000) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(wait_ms)
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out), full_page=False)
    print(f"  → {out}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rf", default="http://127.0.0.1:8082", help="RF display UI URL")
    parser.add_argument("--battlespace", default="http://127.0.0.1:8081", help="Battlespace UI URL")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && python3 -m playwright install chromium", file=sys.stderr)
        return 1

    rf = args.rf.rstrip("/")
    bs = args.battlespace.rstrip("/")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = browser.new_page(viewport={"width": 1600, "height": 900})

        wait_url(f"{rf}/")
        snap(page, rf, IMG / "01-rf-overview.png", 8000)

        with urlopen(f"{rf.replace('8082', '8005')}/api/picture", timeout=10) as resp:
            picture = json.load(resp)
        (IMG / "02-rf-picture-summary.json").write_text(
            json.dumps(
                {
                    "sim_minutes": picture.get("sim_minutes"),
                    "deconfliction_summary": picture.get("deconfliction_summary"),
                    "conflict_count": len(picture.get("conflicts", [])),
                    "emitter_count": len(picture.get("emitters", [])),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  → {IMG / '02-rf-picture-summary.json'}")

        snap(page, f"{rf}/?highlight=HVT-SA6-01", IMG / "03-rf-sa6-highlight.png", 10000)

        try:
            wait_url(f"{bs}/", timeout=15)
            snap(page, f"{bs}/?tab=tasking", IMG / "04-battlespace-tasking-sead.png", 12000)
        except TimeoutError:
            print("  battlespace UI not running — skip tasking screenshot")

        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
