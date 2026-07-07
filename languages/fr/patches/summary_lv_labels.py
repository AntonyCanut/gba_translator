#!/usr/bin/env python3
"""Convert the summary-screen level prefix « Lv » to the French « N. ».

The **Résumé / Infos Pokémon** screen (team list → A → Infos) shows « Lv » in
two places, and both are the FRLG *extra-symbol* glyph #5 — the two raw bytes
``<0xF9><0x05>`` (``EMOJI`` prefix + symbol index 5), NOT a pointed CFRU string
(that was the Panthéon string ``0x4160F4``, fixed in B-236) and NOT the party
ligature glyph (codepoint 0x05 @ ``0x1ECFA0``, fix F-114). Both were ruled out
empirically with in-engine before/after captures; patching either has no effect
on the Résumé.

Two mechanisms use the ``<0xF9><0x05>`` "Lv" symbol here:

1. **Header « Lv10 »** (top-right, next to the Pokémon icon). Drawn by code
   from the standalone string ``gText_Lv`` — the isolated three bytes
   ``F9 05 FF`` at ``0x416223`` (four live pointers). Replacing its two symbol
   bytes with the text « N. » (``C8 AD``) turns the header into « N.10 ».

2. **Memo « … au Lv 10. »** (bottom box). The met-location templates
   (``Rencontré à …, au {LV_2} {LEVEL}.`` and its egg/fateful-encounter
   variants) carry ``<0xF9><0x05>`` inline as the level prefix. It cannot be
   fixed by editing ``combined_fr.txt``: ``{LV_2}`` is a *positional*
   passthrough token — the builder pops the next English control sequence for
   every ``{token}`` regardless of name, so dropping ``{LV_2}`` would make the
   trailing ``{LEVEL}`` bind to the ``F9 05`` sequence and mis-render the level
   number. Rewriting the final bytes in place (same length: 2→2) is the safe
   fix. Every ``F9 05 00 F7`` site (« Lv » symbol + space + dynamic level) is
   rewritten to « N. » + space + dynamic level.

Both edits are strict and length-preserving (``F9 05`` → ``C8 AD``), so no
pointer or free-space bookkeeping is needed. The patch is idempotent: sites
already showing « N. » are skipped, and unexpected bytes are reported and left
untouched rather than corrupted.

Verified in mGBA (savestate slot 2 → Résumé): header « Lv10 » → « N.10 » and
memo « au Lv 10. » → « au N. 10. », with the level number preserved.

Runs in the ``build-fr`` chain after the text injection / summary_labels pass.

Usage::

    python3 languages/fr/patches/summary_lv_labels.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

GBA_BASE = 0x08000000

# FRLG extra-symbol #5 = « Lv »  →  the ASCII/CFRU bytes for « N. ».
LV_SYMBOL = bytes([0xF9, 0x05])   # EMOJI prefix + symbol index 5
ND_TEXT = bytes([0xC8, 0xAD])     # 'N' + '.'  (CFRU charmap)


def _find_all(rom: bytes, pat: bytes) -> list[int]:
    out: list[int] = []
    i = rom.find(pat)
    while i != -1:
        out.append(i)
        i = rom.find(pat, i + 1)
    return out


def _has_live_pointer(rom: bytes, str_off: int) -> bool:
    """True if a word-aligned little-endian pointer to *str_off* exists."""
    ptr = (GBA_BASE + str_off).to_bytes(4, "little")
    i = rom.find(ptr)
    while i != -1:
        if i % 4 == 0:
            return True
        i = rom.find(ptr, i + 1)
    return False


def _patch_header(rom: bytearray) -> int:
    """Rewrite the standalone gText_Lv « Lv » string(s) to « N. ».

    Targets isolated ``FF F9 05 FF`` sequences (a 2-byte string bounded by
    terminators) that have at least one live pointer — i.e. gText_Lv at
    0x416223. Returns the number of strings patched.
    """
    patched = 0
    # Isolated « Lv » string already converted → « N. »?
    for j in _find_all(bytes(rom), bytes([0xFF]) + ND_TEXT + bytes([0xFF])):
        if _has_live_pointer(bytes(rom), j + 1):
            print(f"  header gText_Lv (0x{j + 1:07X}): already « N. » — no change")
    for j in _find_all(bytes(rom), bytes([0xFF]) + LV_SYMBOL + bytes([0xFF])):
        str_off = j + 1
        if not _has_live_pointer(bytes(rom), str_off):
            continue  # dead copy — leave it
        rom[str_off:str_off + 2] = ND_TEXT
        patched += 1
        print(f"  header gText_Lv (0x{str_off:07X}): « Lv » → « N. »")
    return patched


def _patch_memos(rom: bytearray) -> int:
    """Rewrite every « Lv » level-prefix symbol that precedes a dynamic level.

    The pattern ``F9 05 00 F7`` (« Lv » symbol, space, dynamic-level control)
    uniquely marks the met-location memo level prefix. Rewrites the symbol
    bytes to « N. ». Returns the number of sites patched.
    """
    patched = 0
    tail = bytes([0x00, 0xF7])  # space + dynamic control (the level number)
    for j in _find_all(bytes(rom), LV_SYMBOL + tail):
        rom[j:j + 2] = ND_TEXT
        patched += 1
    if patched:
        print(f"  memo level prefix « Lv » → « N. »: {patched} site(s)")
    return patched


def apply_patch(rom_path: Path) -> int:
    rom = bytearray(rom_path.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {rom_path}")

    total = _patch_header(rom) + _patch_memos(rom)
    if total:
        rom_path.write_bytes(rom)
    else:
        print("  summary « Lv » labels: already up to date — no changes")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path,
                        default=Path("output/roms/GenedRom-fr.gba"))
    # Accepted for Makefile call-site symmetry with other summary patches;
    # this patch operates purely on the FR ROM and needs no EN source.
    parser.add_argument("--source", type=Path, default=None)
    args = parser.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    n = apply_patch(args.rom)
    print(f"patch_summary_lv_labels_fr: {n} « Lv » site(s) → « N. »")


if __name__ == "__main__":
    main()
