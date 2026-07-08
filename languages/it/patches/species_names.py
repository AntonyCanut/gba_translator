#!/usr/bin/env python3
"""Italian port of ``patch_species_names`` — patches the fixed-width 11-byte
species-name table (0x166A997, 1293 entries) sourced from
``languages/it/combined_it.txt``'s entries at 0x166A997 + index*11.

The French implementation is fully data-driven (``--combined``), so this
wrapper only re-points it at the Italian data. See
``src.i18n.fr_patch_delegate`` for the delegation mechanism and
``languages/fr/patches/species_names.py`` for the table layout.
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
        "species_names.py",
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
