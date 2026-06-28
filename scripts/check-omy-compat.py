#!/usr/bin/env python3
"""Check compat/tested-against.json against o-my and o-my-sim extension manifests."""
import json
import subprocess
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
omy_root = Path(__import__("os").environ.get("OMY_ROOT", repo_root.parent / "o-my"))
omysim_root = Path(__import__("os").environ.get("OMYSIM_ROOT", repo_root.parent / "o-my-sim"))

script = omy_root / "scripts" / "check-omy-compat.py"
if not script.is_file():
    print(f"o-my not found at {omy_root}", file=sys.stderr)
    sys.exit(2)

subprocess.run(
    [
        sys.executable,
        str(script),
        "--omy-root",
        str(omy_root),
        "--tested-against",
        str(repo_root / "compat" / "tested-against.json"),
    ],
    check=True,
)

ext_path = omysim_root / "compat" / "extension.manifest.json"
tested_path = repo_root / "compat" / "tested-against.json"
if ext_path.is_file() and tested_path.is_file():
    ext = json.loads(ext_path.read_text(encoding="utf-8"))
    tested = json.loads(tested_path.read_text(encoding="utf-8"))
    required = tested.get("requires", {}).get("o_my_sim_extension_contract_id")
    if required and ext.get("contract_id") != required:
        print(
            f"INCOMPATIBLE: o-my-sim extension {ext.get('contract_id')} != required {required}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"o-my-sim extension OK: {ext.get('contract_id')}")
