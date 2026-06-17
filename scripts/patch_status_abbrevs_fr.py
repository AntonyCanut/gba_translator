#!/usr/bin/env python3
"""Patch status condition abbreviations from English to official French.

The Pokémon summary screen reads 3-letter status abbreviations from fixed
addresses referenced by a pointer table at 0x3DFE18 (stride 8):

  0x3DFE18 → SLP (Sleep)     → SOM (Sommeil)
  0x3DFE20 → PSN (Poison)    → EMP (Empoisonné)
  0x3DFE28 → PAR (Paralysis) → PAR (no change)
  0x3DFE30 → BRN (Burn)      → BRL (Brûlure)
  0x3DFE38 → FRZ (Frozen)    → GEL (Gelé)

These 3-char strings end with 0xFF and live at fixed EN-ROM addresses, so
in-place replacement works exactly (3 bytes → 3 bytes, 0xFF terminator kept).
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.text_codec import POKEMON_TABLE

ENC = POKEMON_TABLE
REV = {v: k for k, v in ENC.items()}
GBA_BASE = 0x08000000

# Pointer table base and stride
PTR_TABLE_OFFSET = 0x3DFE18
PTR_STRIDE = 8  # 4-byte pointer + 4 bytes padding

# (EN text, FR text) — PAR unchanged, no entry needed
STATUS_PATCHES = [
    ("SLP", "SOM"),  # index 0 — Sommeil
    ("PSN", "EMP"),  # index 1 — Empoisonné
    # index 2 = PAR, keep as-is
    ("BRN", "BRL"),  # index 3 — Brûlure
    ("FRZ", "GEL"),  # index 4 — Gelé
]
# Which table indices to patch (skip PAR at index 2)
STATUS_INDICES = [0, 1, 3, 4]


def _encode(text: str) -> bytes:
    return bytes([ENC[c] for c in text])


def _decode_at(rom: bytearray, off: int, maxlen: int = 8) -> str:
    chars = []
    for i in range(maxlen):
        b = rom[off + i]
        if b == 0xFF:
            break
        chars.append(REV.get(b, f"[{b:02X}]"))
    return "".join(chars)


def apply_patches(rom_path: Path, dry_run: bool = False) -> int:
    rom = bytearray(rom_path.read_bytes())
    changes = 0

    for idx, (en_text, fr_text) in zip(STATUS_INDICES, STATUS_PATCHES):
        ptr_off = PTR_TABLE_OFFSET + idx * PTR_STRIDE
        ptr_raw = struct.unpack_from("<I", rom, ptr_off)[0]
        file_off = ptr_raw - GBA_BASE

        if not (0 < file_off < len(rom)):
            print(
                f"  WARN index={idx}: pointer 0x{ptr_raw:08X} out of range — skip",
                file=sys.stderr,
            )
            continue

        current = _decode_at(rom, file_off)
        if current == fr_text:
            continue  # already patched
        if current != en_text:
            print(
                f"  WARN 0x{file_off:06X} (index={idx}): expected «{en_text}» got «{current}» — skip",
                file=sys.stderr,
            )
            continue

        fr_encoded = _encode(fr_text)
        en_len = len(en_text)
        fr_len = len(fr_encoded)
        if fr_len > en_len:
            print(
                f"  ERROR 0x{file_off:06X}: FR «{fr_text}» ({fr_len}) > EN «{en_text}» ({en_len}) — skip",
                file=sys.stderr,
            )
            continue

        if not dry_run:
            rom[file_off : file_off + fr_len] = fr_encoded
            # Pad any remaining bytes with 0xFF terminator
            for j in range(fr_len, en_len):
                rom[file_off + j] = 0xFF

        print(f"  0x{file_off:06X}  «{en_text}» → «{fr_text}»")
        changes += 1

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
    print(f"patch_status_abbrevs_fr: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
