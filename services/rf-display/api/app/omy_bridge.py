"""Load o-my-only uci_common modules while GulfWarEngine uses o-my-sim."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

_OMY_ROOT = Path(os.environ.get("OMY_ROOT", Path(__file__).resolve().parents[4].parent / "o-my"))
_OMY_SRC = _OMY_ROOT / "packages/uci_common/src"


def _ensure_omy_on_path() -> None:
    s = str(_OMY_SRC)
    if s not in sys.path:
        sys.path.append(s)


def load_omy_module(relative: str) -> ModuleType:
    """Load a module file from o-my uci_common (e.g. uci_common/commlink_display.py)."""
    _ensure_omy_on_path()
    uci_name = relative.replace("/", ".").replace(".py", "")
    if uci_name in sys.modules:
        return sys.modules[uci_name]
    path = _OMY_SRC / relative
    mod_name = "_omy_" + relative.replace("/", "_").replace(".py", "")
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load o-my module: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    sys.modules[uci_name] = mod
    spec.loader.exec_module(mod)
    return mod


def build_commlink_display(*args, **kwargs):
    return load_omy_module("uci_common/commlink_display.py").build_commlink_display(*args, **kwargs)


def emso_deconfliction_engine(*args, **kwargs):
    load_omy_module("uci_common/emso_messages.py")
    return load_omy_module("uci_common/emso_deconfliction.py").EmsoDeconflictionEngine(*args, **kwargs)


def parse_emso_conflict_xml(xml_body: str):
    return load_omy_module("uci_common/emso_messages.py").parse_emso_conflict_xml(xml_body)


def parse_spectrum_analytics_xml(xml_body: str):
    return load_omy_module("uci_common/analytics_messages.py").parse_spectrum_analytics_xml(xml_body)
