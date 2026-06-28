#!/usr/bin/env python3
"""Capture Gulf War presentation screenshots — tabs, header metrics, attention rail."""
from __future__ import annotations

import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images"
PRES = IMG / "presentation"
METRICS = PRES / "metrics"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5173"


def click_tab(page, label: str) -> None:
    page.locator("nav.tabs button").filter(has_text=re.compile(label, re.I)).first.click()


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && python3 -m playwright install chromium", file=sys.stderr)
        return 1

    PRES.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        try:
            page.request.post(f"{BASE.rstrip('/')}/api/demo/reset")
            print("  reset → T+0 ATO + all feeds")
        except Exception as exc:
            print(f"  reset skipped: {exc}")
        page.wait_for_timeout(5000)

        def snap(name: str, subdir: Path | None = None) -> None:
            page.wait_for_timeout(1500)
            dest = (subdir or IMG) / name
            page.screenshot(path=str(dest), full_page=False)
            print(f"  → {dest}")

        print("Header metrics at T~12 …")
        page.locator(".stat-cards .stat").nth(0).screenshot(path=str(METRICS / "metric-entities.png"))
        (METRICS / "metric-entities.txt").write_text(
            "Entities — correlated track count (threat_picture.entity_count)\n", encoding="utf-8"
        )
        page.locator(".stat-cards .stat").nth(1).screenshot(path=str(METRICS / "metric-air-threats.png"))
        (METRICS / "metric-air-threats.txt").write_text(
            "Air — OPFOR air domain tracks (threat_picture.air_threats)\n", encoding="utf-8"
        )
        page.locator(".stat-cards .stat").nth(2).screenshot(path=str(METRICS / "metric-surface-threats.png"))
        (METRICS / "metric-surface-threats.txt").write_text(
            "Surface — OPFOR surface domain tracks (threat_picture.surface_threats)\n", encoding="utf-8"
        )
        page.locator(".stat-cards .stat").nth(3).screenshot(path=str(METRICS / "metric-active-tasks.png"))
        (METRICS / "metric-active-tasks.txt").write_text(
            "Tasks — open CAOC assignments NEW…ACCEPTED (threat_picture.active_tasks)\n", encoding="utf-8"
        )
        page.locator(".stat-cards .stat").nth(4).screenshot(path=str(METRICS / "metric-sim-clock.png"))
        (METRICS / "metric-sim-clock.txt").write_text(
            "Sim — scenario clock T+MM:SS from picture.sim_minutes\n", encoding="utf-8"
        )
        page.locator(".mission-thread").screenshot(path=str(METRICS / "metric-f2t2ea-phases.png"))
        (METRICS / "metric-f2t2ea-phases.txt").write_text(
            "F2T2EA phase rail — per-phase kill-chain counts (mission_thread.phase_counts)\n",
            encoding="utf-8",
        )
        page.locator(".attention-rail").screenshot(path=str(METRICS / "metric-attention-rail.png"))
        (METRICS / "metric-attention-rail.txt").write_text(
            "Attention rail — TST, pop-up, target, and task queue (picture.attention_queue)\n",
            encoding="utf-8",
        )

        milestones = [
            ("00-decisions-ato-t0.png", "Decisions", 6, PRES),
            ("00b-advisor-suggestions.png", "Decisions", 18, PRES),
            ("01-battlespace-early.png", "Battlespace", 12, PRES),
            ("02-sources-feeds-live.png", "Sources", 20, PRES),
            ("03-tracks-registry.png", "Tracks", 30, PRES),
            ("04-killchain-sa6-find.png", "Kill chain", 40, PRES),
            ("05-decisions-sead-queue.png", "Decisions", 55, PRES),
            ("06-assess-bda.png", "Assess", 70, PRES),
        ]

        t0 = time.time()
        for filename, tab, wait_until_sec, folder in milestones:
            delay = max(0, wait_until_sec - (time.time() - t0))
            if delay > 0:
                print(f"Waiting {delay:.0f}s until T~{wait_until_sec}s → {filename} ...")
                page.wait_for_timeout(int(delay * 1000))
            click_tab(page, tab)
            snap(filename, folder)

        print("FKCM row selection ...")
        click_tab(page, "Kill chain")
        page.wait_for_timeout(1500)
        for sel in (".target-card", ".fkcm-panel tbody tr", ".killchain-panel tbody tr", ".dg-table tbody tr"):
            row = page.locator(sel).first
            if row.count() > 0:
                try:
                    row.scroll_into_view_if_needed(timeout=2000)
                    row.click(force=True, timeout=2000)
                    page.wait_for_timeout(1000)
                    break
                except Exception:
                    continue
        snap("07-killchain-target-selected.png", PRES)

        print("README tab set (dense picture) ...")
        page.wait_for_timeout(10000)
        for name, tab in [
            ("gulfwar-map.png", "Battlespace"),
            ("gulfwar-tracks.png", "Tracks"),
            ("gulfwar-sources.png", "Sources"),
            ("gulfwar-advisor.png", "Decisions"),
            ("gulfwar-decisions.png", "Decisions"),
            ("gulfwar-assess.png", "Assess"),
            ("gulfwar-killchain.png", "Kill chain"),
        ]:
            click_tab(page, tab)
            snap(name, IMG)

        for src, dst in [
            ("gulfwar-sources.png", "gulfwar-fusion.png"),
            ("gulfwar-decisions.png", "gulfwar-tasking.png"),
        ]:
            s, d = IMG / src, IMG / dst
            if s.exists():
                shutil.copy(s, d)

        browser.close()

    print(f"\nPresentation: {PRES}")
    print(f"Metrics: {METRICS}")
    print(f"README: {IMG}/gulfwar-*.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
