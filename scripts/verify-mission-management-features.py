#!/usr/bin/env python3
"""Verify mission-management Phase 1 feature checks."""

from __future__ import annotations

import sys
from pathlib import Path

BM_ROOT = Path(__file__).resolve().parents[1]
API = BM_ROOT / "services" / "battlespace-display" / "api"
sys.path.insert(0, str(API))

from app.mission.harness import all_mission_features_pass, verify_mission_features  # noqa: E402


def main() -> int:
    results = verify_mission_features()
    failed = [r for r in results if not r["passed"]]
    for r in results:
        mark = "✓" if r["passed"] else "✗"
        print(f"{mark} {r['id']}: {r['label']} ({r.get('detail', '')})")
    if failed:
        print(f"Mission management features: FAIL ({len(failed)} failed)", file=sys.stderr)
        return 1
    print(f"Mission management features: PASS ({len(results)} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
