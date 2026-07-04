#!/usr/bin/env python3
"""Verify RF display feature harness — all checks must pass."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import urlopen

BM_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = BM_ROOT / "services" / "rf-display" / "api"
OMY_ROOT = Path(BM_ROOT.parent / "o-my")

sys.path.insert(0, str(API_ROOT))
sys.path.insert(0, str(OMY_ROOT / "packages" / "uci_common/src"))


def verify_local() -> dict:
    from app.rf_harness import all_features_pass, build_harness_picture, verify_rf_features

    picture = build_harness_picture()
    checks = verify_rf_features(picture)
    return {"passed": all_features_pass(checks), "harness_mode": True, "checks": checks}


def verify_remote(base_url: str) -> dict:
    with urlopen(f"{base_url.rstrip('/')}/api/harness/verify", timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify RF display feature harness")
    parser.add_argument("--api", default="", help="API base URL (default: run local harness)")
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    args = parser.parse_args()

    result = verify_remote(args.api) if args.api else verify_local()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for check in result.get("checks", []):
            mark = "✓" if check.get("passed") else "✗"
            detail = f" — {check['detail']}" if check.get("detail") else ""
            print(f"{mark} {check.get('label', check.get('id'))}{detail}")
        status = "PASS" if result.get("passed") else "FAIL"
        print(f"\nRF display feature harness: {status}")

    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
