#!/usr/bin/env python3
"""Generate replacement score/combo/judge assets from the INI config."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "tools" / "replace_digit_assets.py"
CONFIG = ROOT / "tools" / "replace_digit_assets.ini"


def load_tool():
    spec = importlib.util.spec_from_file_location("replace_digit_assets", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    tool = load_tool()
    return tool.main(["--config", str(CONFIG), *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
