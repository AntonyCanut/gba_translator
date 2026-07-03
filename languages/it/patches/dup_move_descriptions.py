#!/usr/bin/env python3
"""Italian port of ``patch_dup_move_descriptions_fr`` — terminates every consumer
of an overflowing Italian move/field-move description (anti-freeze), sourcing the
text from ``languages/it/combined_it.txt``.

Data-driven (``--combined`` + ``--reference-rom``); this wrapper only re-points
the French implementation at the Italian combined file.
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
        "patch_dup_move_descriptions_fr.py",
        rom,
        combined=IT_COMBINED,
        reference_rom=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    return run(make_command(args.rom))


if __name__ == "__main__":
    raise SystemExit(main())
