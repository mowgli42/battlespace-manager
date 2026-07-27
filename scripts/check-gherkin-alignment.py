#!/usr/bin/env python3
"""Ensure operator Gherkin @check: tags match harness feature-check IDs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

BM_ROOT = Path(__file__).resolve().parents[1]
FEATURES_ROOT = BM_ROOT / "features"

# Display → (feature glob, harness module path relative to BM_ROOT, checks attr)
DISPLAYS: list[tuple[str, str, str, str]] = [
    (
        "entity-display",
        "entity-display/*.feature",
        "services/entity-display/api/app/entity_harness.py",
        "ENTITY_FEATURE_CHECKS",
    ),
    (
        "battlespace-display",
        "battlespace-display/*.feature",
        "services/battlespace-display/api/app/battlespace_harness.py",
        "BATTLESPACE_FEATURE_CHECKS",
    ),
    (
        "rf-display",
        "rf-display/*.feature",
        "services/rf-display/api/app/rf_harness.py",
        "RF_FEATURE_CHECKS",
    ),
]

CHECK_TAG_RE = re.compile(r"@check:([A-Za-z0-9_]+)")
CHECKS_ASSIGN_RE = re.compile(
    r"^(?P<name>[A-Z_]+_FEATURE_CHECKS)\s*(?::[^=]+)?=\s*\[(?P<body>.*?)\]\s*$",
    re.MULTILINE | re.DOTALL,
)
CHECK_ID_RE = re.compile(r'\(\s*"(?P<id>[A-Za-z0-9_]+)"\s*,')


def _load_check_ids(harness_path: Path, attr: str) -> set[str]:
    text = harness_path.read_text(encoding="utf-8")
    for match in CHECKS_ASSIGN_RE.finditer(text):
        if match.group("name") != attr:
            continue
        return {m.group("id") for m in CHECK_ID_RE.finditer(match.group("body"))}
    raise SystemExit(f"Could not parse {attr} from {harness_path}")


def _feature_check_tags(feature_paths: list[Path]) -> set[str]:
    tags: set[str] = set()
    for path in feature_paths:
        tags.update(CHECK_TAG_RE.findall(path.read_text(encoding="utf-8")))
    return tags


def main() -> int:
    errors: list[str] = []
    for display, glob_pat, harness_rel, attr in DISPLAYS:
        feature_dir = FEATURES_ROOT / display
        features = sorted(FEATURES_ROOT.glob(glob_pat))
        if not features:
            errors.append(f"{display}: no feature files under {feature_dir}")
            continue
        harness_path = BM_ROOT / harness_rel
        if not harness_path.is_file():
            errors.append(f"{display}: missing harness module {harness_rel}")
            continue
        known = _load_check_ids(harness_path, attr)
        tagged = _feature_check_tags(features)
        unknown = sorted(tagged - known)
        missing = sorted(known - tagged)
        if unknown:
            errors.append(f"{display}: unknown @check tags {unknown}")
        if missing:
            errors.append(f"{display}: harness checks not covered by Gherkin {missing}")
        else:
            print(f"✓ {display}: {len(features)} feature file(s), {len(tagged)} check tags aligned")

    if errors:
        for err in errors:
            print(f"✗ {err}", file=sys.stderr)
        return 1
    print("Gherkin ↔ harness alignment: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
