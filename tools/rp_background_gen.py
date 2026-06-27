"""Drop-in CLI replacement using the Rhythm Prism background conversion."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

import converter


def main() -> int:
    # Keep the pjsekai_background_gen.py command-line contract unchanged.
    if len(sys.argv) < 2:
        print(f"usage: {Path(sys.argv[0]).name} <cover.png> [-v 1|-v 3]", file=sys.stderr)
        return 2

    cover_path = Path(sys.argv[1]).resolve()
    version = "3"
    if len(sys.argv) >= 4 and sys.argv[2] == "-v":
        version = sys.argv[3]

    # v1 and v3 intentionally use the same Rhythm Prism conversion.
    jacket = converter.conv_jacket(cover_path.read_bytes())
    output: Image.Image | None = None
    try:
        output = converter.gen_orig_background(jacket)
        output_path = cover_path.with_name("cover.output.png")
        output.save(output_path)
    finally:
        jacket.close()
        if output is not None:
            output.close()

    print(f"generated {output_path} using {converter.RPRISM_ASSETS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
