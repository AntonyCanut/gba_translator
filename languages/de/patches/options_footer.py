#!/usr/bin/env python3
"""Patch the Options-menu page-2 button legend at 0x1F4E244 (German).

Port of ``patch_options_footer_fr.py`` — same in-place button-icon legend:

    "<0xF8><0x0A>Wählen <0xF8>ÎWechseln <0xF8> <0xF8>ÀOK
     <0xFC>ÀÈ<0xFC>ÂÇ<0xF8>Á<0xF8>ÂMehr"

This string is absent from the English extraction JSON (the string-finder's
heuristic requires a printable first byte; this one starts with the raw
button-icon control code 0xF8 0x0A), so it never reaches ``combined_de.txt``
/ the injection JSON — same class as ``patch_status_abbrevs_fr.py``. No
pointer to it was found either, so it is a direct in-place patch, tightly
packed against the next string (0x1F4E26F), leaving 42 content bytes + 0xFF
available. The button-icon and color/shadow control codes are copied
byte-for-byte from the English original; only the printable words change.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import CHAR_TO_BYTE

OFFSET = 0x1F4E244
SLOT_SIZE = 42  # bytes available before the next packed string (0x1F4E26F)

EN_ORIGINAL = bytes.fromhex(
    "f80acaddd7df00f80bcdebdde8d7dc00f800f801bde3e2dadde6e100"
    "fc0105fc0304f802f803c7e3e6d9"
)

DE_WORDS = ("Wählen", "Wechseln", "OK", "Mehr")


def _encode(word: str) -> bytes:
    return bytes(CHAR_TO_BYTE[c] for c in word)


def _build_de_bytes() -> bytes:
    pick, switch, confirm, more = (_encode(w) for w in DE_WORDS)
    return (
        b"\xf8\x0a" + pick + b"\x00"
        + b"\xf8\x0b" + switch + b"\x00"
        + b"\xf8\x00" + b"\xf8\x01" + confirm + b"\x00"
        + b"\xfc\x01\x05" + b"\xfc\x03\x04"
        + b"\xf8\x02" + b"\xf8\x03" + more
    )


def apply_patch(rom_path: Path, dry_run: bool = False) -> int:
    rom = bytearray(rom_path.read_bytes())
    current = bytes(rom[OFFSET : OFFSET + len(EN_ORIGINAL)])
    de_bytes = _build_de_bytes()

    if current == de_bytes:
        print("patch_options_footer_de: already applied (0 patch(es))")
        return 0

    if current != EN_ORIGINAL:
        print(
            f"  WARN 0x{OFFSET:07X}: expected EN original, found {current.hex()} — skip",
            file=sys.stderr,
        )
        return 0

    if len(de_bytes) + 1 > SLOT_SIZE:
        print(
            f"  ERROR 0x{OFFSET:07X}: DE bytes ({len(de_bytes)}) exceed slot ({SLOT_SIZE - 1}) — skip",
            file=sys.stderr,
        )
        return 0

    if not dry_run:
        rom[OFFSET : OFFSET + len(de_bytes)] = de_bytes
        rom[OFFSET + len(de_bytes)] = 0xFF
        rom_path.write_bytes(rom)

    print(f"  0x{OFFSET:07X}  options-menu footer legend → DE")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n = apply_patch(args.rom, dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_options_footer_de: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
