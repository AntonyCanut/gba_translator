#!/usr/bin/env python3
"""Convert the « Lv » level prefix to the French « N. » (Résumé + party list).

The **Résumé / Infos Pokémon** screen (team list → A → Infos) AND the **party
list** itself (START → Pokémon, e.g. « Lv10 ») show « Lv » as the FRLG
*extra-symbol* glyph #5 — the two raw bytes ``<0xF9><0x05>`` (``EMOJI`` prefix +
symbol index 5), NOT a pointed ASCII CFRU string spelled « Lv » (that was the
Panthéon string ``0x4160F4``, fixed in B-236) and NOT the party ligature glyph
(codepoint 0x05 @ ``0x1ECFA0``, fix F-113 — proven inert: it is patched to « N. »
in the build yet the party list still read « Lv » until this string fix landed).
All were ruled out empirically with in-engine before/after captures + mGBA
watchpoints.

Two mechanisms use the ``<0xF9><0x05>`` "Lv" symbol here:

1. **Header « Lv10 »** (top-right, next to the Pokémon icon). Drawn by code
   from the standalone string ``gText_Lv`` — the isolated three bytes
   ``F9 05 FF`` at ``0x416223`` (four live pointers). Replacing its two symbol
   bytes with the text « N. » (``C8 AD``) turns the header into « N.10 ».

2. **Memo « … au Lv10. »** (bottom box). The met-location templates
   (``Rencontré à …, au {LV_2} {LEVEL}.`` and its egg/fateful-encounter
   variants) carry ``<0xF9><0x05>`` inline as the level prefix, followed by a
   literal space byte before the dynamic-level control code. It cannot be
   fixed by editing ``combined_fr.txt``: ``{LV_2}`` is a *positional*
   passthrough token — the builder pops the next English control sequence for
   every ``{token}`` regardless of name, so dropping ``{LV_2}`` would make the
   trailing ``{LEVEL}`` bind to the ``F9 05`` sequence and mis-render the level
   number. Rewriting the final bytes in place (same length) is the safe fix.
   Every ``<icon> 00 F7`` site (« Lv » symbol/« N. » text + space + dynamic
   level) is rewritten to « N. », with the space rotated past the level number
   and trailing period to the end of the string (issue #66: a space rendered
   right after « N. » shifted the level digits right, e.g. « N. 14 » instead
   of « N.14 »).

Both edits are strict and length-preserving (``F9 05`` → ``C8 AD``, plus a
same-length rotation for the memo's space byte), so no pointer or free-space
bookkeeping is needed. The patch is idempotent: sites already showing « N. »
with no leading space are skipped, and unexpected bytes are reported and left
untouched rather than corrupted.

Verified in mGBA (savestate slot 2 → Résumé): header « Lv10 » → « N.10 » and
memo « au Lv 10. » → « au N.10. », with the level number preserved.

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
    """Rewrite every standalone ``gText_Lv`` « Lv » string to « N. ».

    Targets each isolated ``F9 05 FF`` sequence (the two-byte « Lv » extra-symbol
    followed by a terminator) that has at least one word-aligned live pointer to
    its start — i.e. a pointed ``gText_Lv`` copy. There are two such copies in the
    ROM and the leading byte differs, so we match on the pointed-string *start*
    rather than requiring a preceding ``FF``:

    * ``0x416223`` (four pointers) — the **Résumé / Panthéon** header « Lv10 ».
    * ``0x26051C`` (three pointers) — the **party-list** level prefix « Lv10 »
      (START → Pokémon). This copy is preceded by ``0x08`` (not ``FF``), so the
      old ``FF F9 05 FF`` filter skipped it, which is why the party list kept
      showing « Lv ». Proven with mGBA watchpoints: the party level code reads
      this string and blits extra-symbol #5's graphic; rewriting the string to
      « N. » makes it read « N.10 » (verified in-engine). Note: the separate
      ``party_lv_label.py`` glyph edit at ``0x1ECFA0`` does *not* affect the party
      list — that glyph is not the one the party level code reads.

    Returns the number of strings patched. Idempotent: copies already showing
    « N. » (``C8 AD FF``) are reported and skipped.
    """
    patched = 0
    # Isolated « Lv » string already converted → « N. »?
    for j in _find_all(bytes(rom), ND_TEXT + bytes([0xFF])):
        if _has_live_pointer(bytes(rom), j):
            print(f"  header gText_Lv (0x{j:07X}): already « N. » — no change")
    for j in _find_all(bytes(rom), LV_SYMBOL + bytes([0xFF])):
        if not _has_live_pointer(bytes(rom), j):
            continue  # dead copy / coincidental code bytes — leave it
        rom[j:j + 2] = ND_TEXT
        patched += 1
        print(f"  header gText_Lv (0x{j:07X}): « Lv » → « N. »")
    return patched


def _patch_memos(rom: bytearray) -> int:
    """Rewrite every « Lv »/« N. » level-prefix that precedes a dynamic level.

    The pattern ``<icon> 00 F7`` (« Lv » symbol or « N. » text, space,
    dynamic-level control) marks the met-location memo level prefix, e.g.
    ``c8 ad 00 f7 01 ad ff`` = « N. » + space + level + « . » + terminator.
    That literal space renders as « N. 10 » (issue #66) instead of « N.10 ».

    This patch runs in place on the built ROM with no repointing, so the
    string cannot shrink. Instead of deleting the space, it is *rotated* to
    the very end of the string (right before its ``0xFF`` terminator), which
    is invisible there as trailing whitespace — same length, no free-space or
    pointer bookkeeping needed. Returns the number of sites patched.
    """
    patched = 0
    tail = bytes([0x00, 0xF7])  # space + dynamic control (the level number)
    for icon in (LV_SYMBOL, ND_TEXT):
        for j in _find_all(bytes(rom), icon + tail):
            end = bytes(rom).find(b"\xff", j)
            if end == -1 or rom[j + 2] != 0x00:
                continue
            rom[j:j + 2] = ND_TEXT
            segment = bytes(rom[j + 2:end])
            rom[j + 2:end] = segment[1:] + bytes([0x00])
            patched += 1
    if patched:
        print(f"  memo level prefix: {patched} site(s) — « N. » space moved to end")
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
