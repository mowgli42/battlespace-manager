#!/usr/bin/env python3
"""Verify entity-display live overlay builder against Gulf War scenario."""

from __future__ import annotations

import sys
from pathlib import Path

BM_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = BM_ROOT / "services" / "entity-display" / "api"
OMYSIM_ROOT = Path(BM_ROOT.parent / "o-my-sim")

sys.path.insert(0, str(API_ROOT))
sys.path.insert(0, str(OMYSIM_ROOT / "packages/uci_common/src"))
sys.path = [
    p
    for p in sys.path
    if not p.endswith("/services/battlespace-display/api")
    and not p.endswith("/services/rf-display/api")
]


def main() -> int:
    from app.detection_overlay import build_live_detection_overlays
    from app.scenario_context import load_scenario, scenario_path

    if not scenario_path().is_file():
        print(f"SKIP — scenario not found: {scenario_path()}")
        return 0

    scenario = load_scenario()
    overlays = build_live_detection_overlays(
        scenario,
        platforms_live={
            "COAL-E3-01": {"latitude": 30.2, "longitude": 48.0, "radar_online": True},
        },
        detected_entity_ids=set(),
        sim_minutes=15.0,
    )
    summary = overlays.get("summary") or {}
    checks = [
        ("fog_zones", summary.get("fog_zone_count", 0) >= 1),
        ("route_corridors", summary.get("route_corridor_count", 0) >= 1),
        ("undetected_threats", summary.get("undetected_threat_count", 0) >= 1),
        ("sensors", summary.get("sensor_count", 0) >= 1),
        ("live_mode", summary.get("live_mode") is True),
    ]
    for name, passed in checks:
        print(f"{'✓' if passed else '✗'} {name}")
    all_pass = all(p for _, p in checks)
    print(f"\nEntity display live overlay builder: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
