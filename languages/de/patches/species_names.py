#!/usr/bin/env python3
"""Patch the German fixed-width species-name table.

``combined_de.txt`` contains the curated German names for almost all species.
The fixed 11-byte GBA table cannot store every modern official name verbatim,
so this patch merges an offline German fallback table and uses it when a
combined-file entry is missing or too long for the cell.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from languages.fr.patches import species_names as base_patch  # noqa: E402

DE_COMBINED = REPO_ROOT / "languages/de/combined_de.txt"
DE_FALLBACK = REPO_ROOT / "languages/de/data/species_names_de_fallback.json"


def _load_fallback(path: Path = DE_FALLBACK) -> dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        base_patch.SPECIES_TABLE_OFFSET
        + (int(species_id) - 1) * base_patch.SPECIES_STRIDE: name
        for species_id, name in raw.items()
    }


def _fits_cell(text: str) -> bool:
    try:
        encoded = base_patch._encode(text)
    except KeyError:
        return False
    return len(encoded) + 1 <= base_patch.SPECIES_STRIDE


def load_translations(
    combined: Path = DE_COMBINED,
    fallback: Path = DE_FALLBACK,
) -> dict[int, str]:
    translations = base_patch._parse_combined(combined)
    for offset, name in _load_fallback(fallback).items():
        current = translations.get(offset)
        if current is None or not _fits_cell(current):
            translations[offset] = name
    return translations


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    data = bytearray(rom_path.read_bytes())
    patched, warnings = base_patch.apply_to_rom(data, load_translations())
    for warning in warnings:
        print(f"  WARN {warning}", file=sys.stderr)
    if patched and not dry_run:
        rom_path.write_bytes(data)
    return patched


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    patched = apply_patches(args.rom, dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_species_names_de: {patched} species name cell(s) patched{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
