#!/usr/bin/env python3
"""Italian delegation of ``patch_givecs_gift_item_fr`` — guards the give-CS gift
item (0x01B5) 44-byte struct against divergence from the English layout.

This patch is language-agnostic: it restores the item struct from the pristine
English ROM (``--source``) and injects no localized text, so the Italian build
runs the identical guard.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.i18n.fr_patch_delegate import build_command, run  # noqa: E402


def make_command(rom: Path) -> list[str]:
    return build_command("patch_givecs_gift_item_fr.py", rom, source=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    return run(make_command(args.rom))


if __name__ == "__main__":
    raise SystemExit(main())
