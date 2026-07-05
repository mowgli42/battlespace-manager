"""Load o-my-sim uci_common modules without shadowing o-my imports."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

_OMYSIM_ROOT = Path(os.environ.get("OMYSIM_ROOT", Path(__file__).resolve().parents[4].parent / "o-my-sim"))
_OMYSIM_SRC = _OMYSIM_ROOT / "packages" / "uci_common" / "src"


def _ensure_omysim_on_path() -> None:
    s = str(_OMYSIM_SRC)
    if s not in sys.path:
        sys.path.append(s)


def load_omysim_module(relative: str) -> ModuleType:
    """Load a module file from o-my-sim uci_common."""
    _ensure_omysim_on_path()
    uci_name = relative.replace("/", ".").replace(".py", "")
    path = _OMYSIM_SRC / relative
    mod_name = "_omysim_" + relative.replace("/", "_").replace(".py", "")
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load o-my-sim module: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


def parse_platform_status_xml(xml_body: str):
    return load_omysim_module("uci_common/gw_messages.py").parse_platform_status_xml(xml_body)


def parse_scenario_clock_xml(xml_body: str):
    return load_omysim_module("uci_common/gulfwar_sim/messages.py").parse_scenario_clock_xml(xml_body)


def topic_platform_status() -> str:
    return load_omysim_module("uci_common/topics.py").TOPIC_PLATFORM_STATUS


def topic_scenario_clock() -> str:
    return load_omysim_module("uci_common/topics.py").TOPIC_SCENARIO_CLOCK
