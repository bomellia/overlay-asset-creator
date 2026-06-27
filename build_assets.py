#!/usr/bin/env python3
"""Generate replacement UI assets from the INI config."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from tools import replace_digit_assets


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        candidates = (Path.cwd(), executable_dir, executable_dir.parent)
        for candidate in candidates:
            if (candidate / "assets").is_dir() and (candidate / "tools" / "replace_digit_assets.ini").is_file():
                return candidate.resolve()
        return executable_dir
    return Path(__file__).resolve().parent


def main() -> int:
    root = application_root()
    if getattr(sys, "frozen", False):
        os.chdir(root)
    config = root / "tools" / "replace_digit_assets.ini"
    return replace_digit_assets.main(["--config", str(config), *sys.argv[1:]])


if __name__ == "__main__":
    raise SystemExit(main())
