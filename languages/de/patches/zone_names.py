#!/usr/bin/env python3
"""Deliver pointer-based zone names and fly banners from DE combined data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.i18n.fr_patch_delegate import build_command, run  # noqa: E402

DE_COMBINED = ROOT / "languages/de/combined_de.txt"


def make_command(rom: Path) -> list[str]:
    # Tail placement makes the EN-free / ES-populated pool safe to use.
    return build_command(
        "patch_zone_names_fr.py",
        rom,
        source=True,
        combined=DE_COMBINED,
        reference_rom=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    return run(make_command(args.rom))


if __name__ == "__main__":
    raise SystemExit(main())
