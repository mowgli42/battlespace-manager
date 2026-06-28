#!/usr/bin/env python3
"""Capture o-my walkthrough screenshots (Playwright, no-sandbox for CI/VM)."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images" / "walkthrough"


def wait_url(url: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=3) as resp:
                if resp.status < 400:
                    return
        except Exception:
            time.sleep(1)
    raise TimeoutError(f"URL not ready: {url}")


def snap(page, url: str, out: Path, wait_ms: int = 8000) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(wait_ms)
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out), full_page=False)
    print(f"  → {out}")


def capture_o_my(page) -> None:
    wait_url("http://127.0.0.1:8080/")
    snap(page, "http://127.0.0.1:8080", IMG / "01-o-my-adsb-map.png", 12000)
    snap(page, "http://127.0.0.1:8003/docs", IMG / "02-o-my-api-docs.png", 4000)
    try:
        wait_url("http://127.0.0.1:8004/health", timeout=5)
        snap(page, "http://127.0.0.1:8004/docs", IMG / "03-o-my-commlink-api.png", 4000)
    except TimeoutError:
        with urlopen("http://127.0.0.1:8003/api/commlinks", timeout=5) as resp:
            data = json.load(resp)
        (IMG / "03-o-my-commlinks.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        print("  → commlink data via display API (memory-bus mode)")


def capture_sim(page, base: str) -> None:
    wait_url(base)
    try:
        page.request.post(f"{base.rstrip('/')}/api/demo/reset")
        print("  reset → T+0 ATO + all feeds")
    except Exception as exc:
        print(f"  reset skipped: {exc}")
    snap(page, base, IMG / "04-sim-battlespace-map.png", 10000)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sim", metavar="URL", help="Capture o-my-sim battlespace map at URL")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && python3 -m playwright install chromium", file=sys.stderr)
        return 1

    IMG.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        if args.sim:
            capture_sim(page, args.sim)
        else:
            capture_o_my(page)
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
