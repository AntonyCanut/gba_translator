#!/usr/bin/env python3
"""Convert the party-menu level prefix « Lv » to the French « N. ».

The party list (START → Pokémon, e.g. « Lv10 ») draws its level prefix as a
single **ligature glyph** — codepoint 0x05 of the non-compressed FRLG font used
by the party box — that renders the two characters « Lv ». It is NOT a pointed
CFRU string and NOT a baked LZ77 box graphic, which is why every text/graphic
pass of the pipeline leaves it untouched and why ticket F-113 first mis-classified
it as a template graphic.

Empirically established (mGBA watchpoints, see
``docs/analysis/party_menu_lv_investigation.md``):

* The party font (``s@1EEF00``) renders exactly ``Embrylex`` / ``10`` / ``♀`` /
  ``30 / 30`` / ``Annuler`` — with **no** « Lv » among the width-measured glyphs.
* A read-watchpoint over the glyph-pixel region finds exactly ONE glyph that is
  read **without** a width-table lookup: codepoint 0x05, pixel data at ROM
  ``0x1ECFA0``. That is the « Lv » ligature, blitted directly by the level code.
* Blanking that glyph erases « Lv » on screen while the « PV » LZ77 label
  (block ``0x008001D0``) survives — proving « Lv » is a font glyph.

Editing this single ligature glyph to « N. » is the clean fix: it covers **every**
screen that shows the level prefix (party list, and any other reader of glyph
0x05), exactly as F-113's own decision tree prescribed for the ligature case.

Glyph format (reverse-engineered by write/observe on mGBA)
----------------------------------------------------------
Each glyph is 32 bytes = 64 nibbles. ``DecompressGlyphTile`` maps nibble ``n`` to
a 2-pixel-wide cell at local (row = ``n // 4``, col = ``3 - (n % 4)``) of a
4-column × 16-row grid. Pixel-value semantics after the printer colour map:
``5`` → white (fg), ``8`` → grey (shadow), ``0`` / ``0xF`` → transparent.

The new « N. » glyph is the ROM's real « N » glyph (codepoint 0xC8) with a white
period dot added in the otherwise-empty right column (rows 9-11), so the letter
keeps the font's native antialiasing and the level reads « N.10 ».

The patch is strict: the 32 bytes at ``0x1ECFA0`` must byte-match the known « Lv »
ligature (or the already-patched « N. »); anything else is reported and skipped
rather than corrupted.

Runs in the ``build-fr`` chain AFTER repair_stable/repair_localized (like
``hp_labels.py``) — see the Makefile.

Usage::

    python3 languages/fr/patches/party_lv_label.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ROM offset of the « Lv » ligature glyph (codepoint 0x05 of the party font).
LV_GLYPH_OFFSET = 0x1ECFA0
GLYPH_SIZE = 32

# Known-good current bytes: the original « Lv » ligature glyph.
OLD_LV_GLYPH = bytes.fromhex(
    "0000ffffffffffffff6fff6fff6f666f666f666f9a56ebaaffff000000000000"
)

# New « N. » glyph: the real « N » glyph (cp 0xC8) + a white period dot in the
# empty right column (nibbles 36/40/44 = local col 3, rows 9-11), value 5 = white.
NEW_ND_GLYPH = bytes.fromhex(
    "0000c0ffc0ffc0ff806d80598059806580658569856d85aec0ff000000000000"
)


def apply_patch(rom_path: Path) -> int:
    rom = bytearray(rom_path.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {rom_path}")

    current = bytes(rom[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE])

    if current == NEW_ND_GLYPH:
        print("  party level label (0x1ECFA0): already « N. » — no change")
        return 0

    if current != OLD_LV_GLYPH:
        print(
            f"  WARN party level label: glyph at 0x{LV_GLYPH_OFFSET:07X} matches "
            f"neither the known « Lv » ligature nor « N. » — skip\n"
            f"       got {current.hex()}",
            file=sys.stderr,
        )
        return 0

    rom[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE] = NEW_ND_GLYPH
    rom_path.write_bytes(rom)
    print("  party level label (0x1ECFA0): « Lv » → « N. »")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path,
                        default=Path("output/roms/GenedRom-fr.gba"))
    args = parser.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    n = apply_patch(args.rom)
    print(f"patch_party_lv_label_fr: {n} glyph patched")


if __name__ == "__main__":
    main()
