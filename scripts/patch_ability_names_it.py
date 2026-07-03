#!/usr/bin/env python3
"""Italian port of ``patch_ability_names_fr`` — patches the fixed-width 17-byte
ability-name table, sourcing the Italian names from ``languages/it/combined_it.txt``
and validating each cell against ``languages/en/combined_en.txt``.

The French implementation is fully data-driven (``--combined`` / ``--combined-en``),
so this wrapper only re-points it at the Italian data. See
``src.i18n.fr_patch_delegate`` for the delegation mechanism.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.i18n.fr_patch_delegate import build_command, run  # noqa: E402

IT_COMBINED = REPO_ROOT / "languages/it/combined_it.txt"
EN_COMBINED = REPO_ROOT / "languages/en/combined_en.txt"


def make_command(rom: Path) -> list[str]:
    return build_command(
        "patch_ability_names_fr.py",
        rom,
        combined=IT_COMBINED,
        combined_en=EN_COMBINED,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    return run(make_command(args.rom))


if __name__ == "__main__":
    raise SystemExit(main())
