#!/usr/bin/env python3
"""Italian port of ``patch_move_names`` — patches the real, fixed-width
13-byte move-name table (0x1B2980, 894 entries) sourced from
``languages/it/combined_it.txt``'s legacy-offset (0xA40A10) entries.

The French implementation is fully data-driven (``--combined``), so this
wrapper only re-points it at the Italian data. See
``src.i18n.fr_patch_delegate`` for the delegation mechanism and
``languages/fr/patches/move_names.py`` for why the legacy offset differs
from the live table address.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from src.i18n.fr_patch_delegate import build_command, run  # noqa: E402

IT_COMBINED = REPO_ROOT / "languages/it/combined_it.txt"


def make_command(rom: Path) -> list[str]:
    return build_command(
        "move_names.py",
        rom,
        combined=IT_COMBINED,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    return run(make_command(args.rom))


if __name__ == "__main__":
    raise SystemExit(main())
