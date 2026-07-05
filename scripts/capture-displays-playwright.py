#!/usr/bin/env python3
"""Capture README screenshots for all operator displays and the portal."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images" / "displays"


def wait_url(url: str, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=3) as resp:
                if resp.status < 400:
                    return
        except Exception:
            time.sleep(1)
    raise TimeoutError(f"URL not ready: {url}")


def snap(page, url: str, out: Path, wait_ms: int = 5000) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(wait_ms)
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out), full_page=False)
    print(f"  → {out.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entity", default="http://127.0.0.1:8080")
    parser.add_argument("--battlespace", default="http://127.0.0.1:8081")
    parser.add_argument("--rf", default="http://127.0.0.1:8082")
    parser.add_argument("--portal", default="http://127.0.0.1:8888")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && python3 -m playwright install chromium", file=sys.stderr)
        return 1

    entity = args.entity.rstrip("/")
    battlespace = args.battlespace.rstrip("/")
    rf = args.rf.rstrip("/")
    portal = args.portal.rstrip("/")

    targets = [
        (f"{entity}/", IMG / "entity-display.png", 8000),
        ("http://127.0.0.1:8003/landing", IMG / "entity-landing.png", 3000),
        (f"{battlespace}/", IMG / "battlespace-display.png", 8000),
        (f"{battlespace}/?tab=killchain", IMG / "battlespace-killchain.png", 6000),
        ("http://127.0.0.1:8004/landing", IMG / "battlespace-landing.png", 3000),
        (f"{rf}/", IMG / "rf-display.png", 8000),
        ("http://127.0.0.1:8005/landing", IMG / "rf-landing.png", 3000),
        (f"{portal}/", IMG / "display-portal.png", 4000),
    ]

    for url, _, _ in targets:
        wait_url(url)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        for url, out, wait_ms in targets:
            snap(page, url, out, wait_ms)
        browser.close()

    print(f"\nScreenshots written to {IMG.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
