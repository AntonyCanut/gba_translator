#!/usr/bin/env python3
"""Italian delegation of ``patch_summary_labels_fr`` — restores the summary-screen
tilemap and localized tileset (Type/OT/Item label boxes) in the built ROM.

This patch is language-agnostic: it restores the English tilemap and copies the
localized tileset from the source ROMs, injecting no French text. The Italian
build runs the identical restore with ``--source``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.i18n.fr_patch_delegate import build_command, run  # noqa: E402


def make_command(rom: Path) -> list[str]:
    return build_command("patch_summary_labels_fr.py", rom, source=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    return run(make_command(args.rom))


if __name__ == "__main__":
    raise SystemExit(main())
