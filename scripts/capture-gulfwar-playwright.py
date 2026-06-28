#!/usr/bin/env python3
"""Capture Gulf War presentation screenshots — tabs, metrics, and operator workflow."""
from __future__ import annotations

import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images"
PRES = IMG / "presentation"
METRICS = PRES / "metrics"
WORKFLOW = PRES / "workflow"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5173"


def sim_api_base() -> str:
    """Sim control hits the API directly (faster than Vite proxy during seek)."""
    for ui_port, api_port in (("8081", "8004"), ("5173", "8004")):
        if f":{ui_port}" in BASE:
            return BASE.replace(f":{ui_port}", f":{api_port}")
    return "http://127.0.0.1:8004"


API = sim_api_base()


def click_tab(page, label: str) -> None:
    page.locator("nav.tabs button").filter(has_text=re.compile(label, re.I)).first.click()


def api_post(page, path: str, body: dict | None = None) -> None:
    url = f"{API.rstrip('/')}{path}"
    if body is None:
        page.request.post(url)
    else:
        page.request.post(url, data=json.dumps(body), headers={"Content-Type": "application/json"})


def seek_sim(page, minutes: float, settle_ms: int = 2200) -> None:
    api_post(page, "/api/sim/pause")
    api_post(page, "/api/sim/seek", {"offset_minutes": minutes})
    page.wait_for_timeout(settle_ms)


def capture_metrics(page) -> None:
    print("Header metrics …")
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
    if page.locator(".stat-cards .stat").count() > 5:
        page.locator(".stat-cards .stat").nth(5).screenshot(path=str(METRICS / "metric-picture-latency.png"))
        (METRICS / "metric-picture-latency.txt").write_text(
            "Update — seconds since last SSE /api/picture payload\n", encoding="utf-8"
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


def capture_workflow(page, snap) -> None:
    """Nominal CAOC operator flow — deterministic seeks on Gulf War scenario."""
    print("\nOperator workflow (seek-based) …")
    WORKFLOW.mkdir(parents=True, exist_ok=True)

    workflow_steps = [
        (
            "01-hud-overview.png",
            None,
            0,
            "Full operator shell at H-hour: header stats, F2T2EA rail, attention queue.",
        ),
        (
            "02-battlespace-milsymbols.png",
            "Battlespace",
            12,
            "Battlespace map with MIL-STD-2525D markers after SAT SIGINT SA-6 cue.",
        ),
        (
            "03-timeline-mission-plan.png",
            "Timeline",
            0,
            "Mission timeline — scenario beats from ATO through upcoming SCUD/SEAD.",
        ),
        (
            "04-sources-feed-health.png",
            "Sources",
            10,
            "Feed fusion panel — Link-16, AWACS, AIS, MTI online with correlation rows.",
        ),
        (
            "05-tracks-registry.png",
            "Tracks",
            15,
            "Entity registry — custody, confidence, and domain for HVT tracks.",
        ),
        (
            "06-attention-scud-tst.png",
            "Battlespace",
            22,
            "SCUD launch — attention rail promotes time-sensitive target.",
        ),
        (
            "07-killchain-sa6-find.png",
            "Kill chain",
            15,
            "FKCM kill chain — SA-6 site in Find after ELINT/MTI cue.",
        ),
        (
            "08-decisions-sead-queue.png",
            "Decisions",
            20,
            "CAOC tasking queue — SEAD assignment against SA-6 HVT.",
        ),
        (
            "09-timeline-scud-imminent.png",
            "Timeline",
            22,
            "Timeline at SCUD launch — imminent scenario beat + open strike tasks.",
        ),
        (
            "10-decisions-strike-tasking.png",
            "Decisions",
            25,
            "Strike tasking against SCUD TEL after IMINT fix.",
        ),
        (
            "11-assess-bda.png",
            "Assess",
            50,
            "BDA panel — TEL destroyed, kill chain in Assess phase.",
        ),
    ]

    captions_path = WORKFLOW / "captions.json"
    captions: list[dict[str, str | float | None]] = []

    for filename, tab, seek_min, caption in workflow_steps:
        seek_sim(page, seek_min)
        if tab:
            click_tab(page, tab)
        snap(filename, WORKFLOW)
        captions.append(
            {
                "file": filename,
                "tab": tab,
                "sim_minutes": seek_min,
                "caption": caption,
            }
        )

    captions_path.write_text(json.dumps(captions, indent=2) + "\n", encoding="utf-8")

    print("Map entity popup (milsymbol + metadata) …")
    seek_sim(page, 15)
    click_tab(page, "Battlespace")
    page.wait_for_timeout(800)
    marker = page.locator(".leaflet-marker-icon.mil-symbol").nth(2)
    if marker.count() > 0:
        try:
            marker.click(force=True, timeout=3000)
            page.wait_for_timeout(600)
            snap("02b-battlespace-entity-popup.png", WORKFLOW)
            captions.append(
                {
                    "file": "02b-battlespace-entity-popup.png",
                    "tab": "Battlespace",
                    "sim_minutes": 15,
                    "caption": "Entity popup — affiliation, domain, confidence from track model.",
                }
            )
            captions_path.write_text(json.dumps(captions, indent=2) + "\n", encoding="utf-8")
        except Exception as exc:
            print(f"  popup skipped: {exc}")

    print("Kill chain row selection …")
    seek_sim(page, 15)
    click_tab(page, "Kill chain")
    page.wait_for_timeout(800)
    for sel in (".target-card", ".fkcm-panel tbody tr", ".killchain-panel tbody tr", ".dg-table tbody tr"):
        row = page.locator(sel).first
        if row.count() > 0:
            try:
                row.scroll_into_view_if_needed(timeout=2000)
                row.click(force=True, timeout=2000)
                page.wait_for_timeout(800)
                break
            except Exception:
                continue
    snap("07b-killchain-target-selected.png", WORKFLOW)

    print("Timeline scenario filter …")
    seek_sim(page, 18)
    click_tab(page, "Timeline")
    page.locator(".tl-filters button").filter(has_text=re.compile("Scenario", re.I)).first.click()
    page.wait_for_timeout(400)
    snap("03b-timeline-scenario-filter.png", WORKFLOW)


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("pip install playwright && python3 -m playwright install chromium", file=sys.stderr)
        return 1

    PRES.mkdir(parents=True, exist_ok=True)
    METRICS.mkdir(parents=True, exist_ok=True)
    WORKFLOW.mkdir(parents=True, exist_ok=True)
    IMG.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 900})
        page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        try:
            api_post(page, "/api/demo/reset")
            print("  reset → T+0 ATO + all feeds")
        except Exception as exc:
            print(f"  reset skipped: {exc}")
        page.wait_for_timeout(4000)

        def snap(name: str, subdir: Path | None = None) -> None:
            page.wait_for_timeout(1200)
            dest = (subdir or IMG) / name
            page.screenshot(path=str(dest), full_page=False)
            print(f"  → {dest}")

        seek_sim(page, 12)
        capture_metrics(page)

        capture_workflow(page, snap)

        milestones = [
            ("00-decisions-ato-t0.png", "Decisions", 0, PRES),
            ("00b-advisor-suggestions.png", "Decisions", 18, PRES),
            ("01-battlespace-early.png", "Battlespace", 12, PRES),
            ("01b-timeline-overview.png", "Timeline", 12, PRES),
            ("02-sources-feeds-live.png", "Sources", 20, PRES),
            ("03-tracks-registry.png", "Tracks", 30, PRES),
            ("04-killchain-sa6-find.png", "Kill chain", 40, PRES),
            ("05-decisions-sead-queue.png", "Decisions", 55, PRES),
            ("06-assess-bda.png", "Assess", 70, PRES),
        ]

        print("\nLegacy presentation milestones (seek-based) …")
        for filename, tab, seek_min, folder in milestones:
            print(f"  T+{seek_min} → {filename}")
            seek_sim(page, seek_min)
            click_tab(page, tab)
            snap(filename, folder)

        print("FKCM row selection (presentation) …")
        seek_sim(page, 40)
        click_tab(page, "Kill chain")
        page.wait_for_timeout(800)
        for sel in (".target-card", ".fkcm-panel tbody tr", ".killchain-panel tbody tr", ".dg-table tbody tr"):
            row = page.locator(sel).first
            if row.count() > 0:
                try:
                    row.scroll_into_view_if_needed(timeout=2000)
                    row.click(force=True, timeout=2000)
                    page.wait_for_timeout(800)
                    break
                except Exception:
                    continue
        snap("07-killchain-target-selected.png", PRES)

        print("README tab set (dense picture) …")
        seek_sim(page, 45)
        for name, tab in [
            ("gulfwar-map.png", "Battlespace"),
            ("gulfwar-timeline.png", "Timeline"),
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

        api_post(page, "/api/sim/resume")
        browser.close()

    print(f"\nWorkflow: {WORKFLOW}")
    print(f"Presentation: {PRES}")
    print(f"Metrics: {METRICS}")
    print(f"README: {IMG}/gulfwar-*.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
