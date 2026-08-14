#!/usr/bin/env python3
"""Restore the German ROM species-name table from the canonical English ROM.

Species names are a fixed table of 1,293 cells, 11 bytes each.  The German
build deliberately does not localise those cells: it copies the complete raw
slice from ``input/roms/englishrom.gba`` so names, terminators and padding are
all byte-identical to the source.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from languages.fr.patches.species_names import (  # noqa: E402
    SPECIES_COUNT,
    SPECIES_STRIDE,
    SPECIES_TABLE_OFFSET,
)

ENGLISH_ROM = REPO_ROOT / "input/roms/englishrom.gba"
SPECIES_TABLE_END = SPECIES_TABLE_OFFSET + SPECIES_COUNT * SPECIES_STRIDE


def restore_species_table(target: bytearray, english: bytes) -> int:
    """Copy every canonical EN cell and return the number of changed cells."""
    if len(target) < SPECIES_TABLE_END or len(english) < SPECIES_TABLE_END:
        raise ValueError(
            "source and target ROMs must contain the complete species table "
            f"through 0x{SPECIES_TABLE_END:X}"
        )

    changed = sum(
        target[offset : offset + SPECIES_STRIDE]
        != english[offset : offset + SPECIES_STRIDE]
        for offset in range(
            SPECIES_TABLE_OFFSET,
            SPECIES_TABLE_END,
            SPECIES_STRIDE,
        )
    )
    target[SPECIES_TABLE_OFFSET:SPECIES_TABLE_END] = english[
        SPECIES_TABLE_OFFSET:SPECIES_TABLE_END
    ]
    return changed


def apply_patches(
    rom_path: Path,
    source: Path = ENGLISH_ROM,
    dry_run: bool = False,
) -> int:
    target = bytearray(rom_path.read_bytes())
    english = source.read_bytes()
    changed = restore_species_table(target, english)
    if changed and not dry_run:
        rom_path.write_bytes(target)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--source", type=Path, default=ENGLISH_ROM)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    changed = apply_patches(args.rom, source=args.source, dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    print(
        "restore_species_names_en: "
        f"{changed}/{SPECIES_COUNT} species name cell(s) restored{suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
