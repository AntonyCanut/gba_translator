#!/usr/bin/env python3
"""Patch the German fixed-width move-name table.

The versioned glossary is aligned to the CFRU table index, not to upstream
move IDs. This matters because CFRU diverges from PokeAPI's numbering: the
old numeric fallback could replace an overflowing move with the German name
of a completely different move. Official glossary names win; Unbound-only
entries fall back to the curated combined file at the same CFRU offset.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from languages.fr.patches import move_names as base_patch  # noqa: E402

DE_COMBINED = REPO_ROOT / "languages/de/combined_de.txt"
DE_OFFICIAL = REPO_ROOT / "languages/de/data/move_names_de_official.json"


def load_official_entries(path: Path = DE_OFFICIAL) -> dict[int, dict[str, str]]:
    """Charge le glossaire indexé par l'ordre réel de la table CFRU."""
    return {
        int(move_index): entry
        for move_index, entry in json.loads(path.read_text(encoding="utf-8")).items()
    }


def _load_official(path: Path = DE_OFFICIAL) -> dict[int, str]:
    return {
        base_patch.LEGACY_TABLE_OFFSET + int(move_id) * base_patch.MOVE_STRIDE:
        entry["official"]
        for move_id, entry in load_official_entries(path).items()
    }


def _fits_cell(text: str) -> bool:
    try:
        encoded = base_patch._encode(text)
    except KeyError:
        return False
    return len(encoded) + 1 <= base_patch.MOVE_STRIDE


def _constrained_display(text: str) -> str:
    """Produit la forme stable d'une cellule CFRU de 12 glyphes maximum."""
    if _fits_cell(text):
        return text
    max_glyphs = base_patch.MOVE_STRIDE - 1
    display = text[: max_glyphs - 1].rstrip(" -") + "."
    if not _fits_cell(display):
        raise ValueError(f"cannot constrain move name {text!r}")
    return display


def load_translations(
    combined: Path = DE_COMBINED,
    official: Path = DE_OFFICIAL,
) -> dict[int, str]:
    start = base_patch.LEGACY_TABLE_OFFSET
    end = start + base_patch.MOVE_STRIDE * base_patch.MOVE_COUNT
    translations = {
        offset: _constrained_display(name)
        for offset, name in base_patch._parse_combined(combined).items()
        if start <= offset < end and (offset - start) % base_patch.MOVE_STRIDE == 0
    }
    for offset, name in _load_official(official).items():
        translations[offset] = _constrained_display(name)
    return translations


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    data = bytearray(rom_path.read_bytes())
    live_base = base_patch.resolve_live_base(data)
    print(f"patch_move_names_de: live table @ 0x{live_base:X}", file=sys.stderr)
    patched, warnings = base_patch.apply_to_rom(
        data,
        load_translations(),
        live_base=live_base,
    )
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
    print(f"patch_move_names_de: {patched} move name cell(s) patched{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
