#!/usr/bin/env python3
"""German port of ``patch_move_names`` — patches the real, fixed-width
13-byte move-name table (live base resolved from the ROM's own pointer, see
``languages/fr/patches/move_names.py``) sourced from
``languages/de/combined_de.txt``'s legacy-offset (0xA40A10) entries.

The French implementation is fully data-driven (``--combined``), so this
wrapper only re-points it at the German data. See
``src.i18n.fr_patch_delegate`` for the delegation mechanism.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from src.i18n.fr_patch_delegate import build_command, run  # noqa: E402

DE_COMBINED = REPO_ROOT / "languages/de/combined_de.txt"


def make_command(rom: Path) -> list[str]:
    return build_command(
        "move_names.py",
        rom,
        combined=DE_COMBINED,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    return run(make_command(args.rom))


if __name__ == "__main__":
    raise SystemExit(main())
