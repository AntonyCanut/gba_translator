#!/usr/bin/env python3
"""Patch the level-up screen stat-change abbreviations to German.

The level-up stat-change display uses two short abbreviations for Special
Attack and Special Defense stats, pointing through a table, one string per
label in game-engine order. Every string is 0xFF-terminated and stores:

    <label text><0xFF>

Two abbreviations at fixed offsets (0x41B2CC and 0x41B2D4 in the EN ROM):
    Ang.Sp.  (Special Attack = Angriff Spezial)
    Ver.Sp.  (Special Defense = Verteidigung Spezial)

Why this is a class-3 *post-build* patch and not a `combined_de.txt` entry:
these strings sit outside the generic builder's pointer-chasing extractor's
reach (they're fixed-table entries, not reachable from the pointer tables
the extractor walks). While they appear in combined_de.txt for reference,
they never reach the built ROM from the pipeline alone. This patch writes
them in place post-build, idempotent and self-healing.

German labels (abbreviated style matching English length):
    Sp. Atk → Ang.Sp.  (Angriff Spezial = Special Attack)
    Sp. Def → Ver.Sp.  (Verteidigung Spezial = Special Defense)

The patch is idempotent: it accepts either the EN original ("Sp. Atk",
"Sp. Def") or the current DE bytes, so re-running over an already-built
ROM converges without a full rebuild.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import POKEMON_TABLE  # noqa: E402

ENC = POKEMON_TABLE
GBA_BASE = 0x08000000

# Fixed offsets in the EN ROM for the two level-up stat abbreviations
_LEVELUP_ABBREVS = [
    {"offset": 0x41B2CC, "en": "Sp. Atk", "de": "Ang.Sp."},
    {"offset": 0x41B2D4, "en": "Sp. Def", "de": "Ver.Sp."},
]


def _encode(text: str) -> bytes:
    """Encode text using the CFRU charmap."""
    return bytes([ENC[c] for c in text])


def _decode_at(rom: bytes, off: int, maxlen: int = 20) -> str:
    """Decode a 0xFF-terminated string from ROM at the given offset."""
    chars = []
    for i in range(maxlen):
        if off + i >= len(rom):
            break
        b = rom[off + i]
        if b == 0xFF:
            break
        # Reverse mapping
        rev = {v: k for k, v in ENC.items()}
        chars.append(rev.get(b, f"[0x{b:02X}]"))
    return "".join(chars)


def apply_to_rom(rom: bytearray, dry_run: bool = False) -> int:
    """Patch stat abbreviations in `rom` in place. Returns the change count."""
    changes = 0

    for entry in _LEVELUP_ABBREVS:
        offset = entry["offset"]
        en_text = entry["en"]
        de_text = entry["de"]

        if offset >= len(rom):
            print(
                f"  WARN 0x{offset:06X}: offset out of range — skip",
                file=sys.stderr,
            )
            continue

        # Decode current bytes
        current = _decode_at(rom, offset)

        # Check if already at target
        if current == de_text:
            continue

        # Accept either EN original or current DE
        if current not in {en_text, de_text}:
            print(
                f"  WARN 0x{offset:06X}: expected one of {en_text!r}, {de_text!r} "
                f"got {current!r} — skip",
                file=sys.stderr,
            )
            continue

        # Encode and patch
        de_encoded = _encode(de_text)
        en_encoded = _encode(en_text)

        if len(de_encoded) > len(en_encoded):
            print(
                f"  ERROR 0x{offset:06X}: DE {de_text!r} ({len(de_encoded)} bytes) "
                f"longer than EN {en_text!r} ({len(en_encoded)} bytes) — skip",
                file=sys.stderr,
            )
            continue

        if not dry_run:
            rom[offset : offset + len(de_encoded)] = de_encoded
            # Pad the freed trailing bytes with 0xFF to preserve the terminator region
            for j in range(len(de_encoded), len(en_encoded)):
                rom[offset + j] = 0xFF

        print(f"  0x{offset:06X}  «{current}» → «{de_text}»")
        changes += 1

    return changes


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    """Apply patches to the ROM file at rom_path."""
    rom = bytearray(rom_path.read_bytes())
    changes = apply_to_rom(rom, dry_run=dry_run)
    if not dry_run and changes:
        rom_path.write_bytes(rom)
    return changes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n = apply_patches(args.rom, dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_levelup_stat_abbreviations_de: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
