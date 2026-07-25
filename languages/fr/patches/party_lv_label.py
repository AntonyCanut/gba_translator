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
4-column × 16-row grid. Each nibble packs *two independent 2-bit palette picks*,
one per pixel of the cell (high 2 bits = left pixel, low 2 bits = right pixel):
palette 1 → white (fg), palette 2 → grey (shadow), palette 0 / 3 → transparent.
So ``5`` (``0101``) = white+white (solid dot ink), ``0xA`` (``1010``) =
grey+grey (solid shadow), ``8`` (``1000``) = grey+transparent (a *half* shadow —
the issue #138 follow-up bug), ``0``/``0xC``/``0xF`` = transparent+transparent,
and the antialiased edges of the real « N » glyph (``6``/``9``/``D``/``E``) mix
one white/grey pixel with one transparent pixel.

The new « N. » glyph is the ROM's real « N » glyph (codepoint 0xC8) with a white
period dot added in the otherwise-empty right column, so the letter keeps the
font's native antialiasing and the level reads « N.10 ».

The dot's drop-shadow was first placed at row 12 (issue #104 fix, commit
5708ee03) — directly below a 3-row (rows 9-11) dot. That renders fine in the
party list (16px line pitch) but issue #138 showed it is WRONG in the in-battle
level-up notification box: that box only gives glyph ink room for nibble rows
4-11 (the exact vertical extent the unmodified « N » letter already uses); row
12 falls into the box's decorative bottom border strip, so the shadow pixel
appeared as a stray dot below the box while the dot itself, inside the box,
showed no shadow at all. Fix (issue #138): keep the dot+shadow entirely within
rows 4-11 — shrink the dot to 2 rows (9-10, still value 5/white) and turn its
former 3rd row (row 11) into the drop-shadow (value 8) instead of adding a new
row 12. Same total ink footprint as the plain « N », so it can never overflow
the box again, in either UI context.

Issue #138 follow-up (reporter's second screenshot): the row-11 shadow was
still visibly incomplete — only its left half rendered grey, the right half
showed through as background. ``DecompressGlyphTile`` packs each nibble as
*two independent 2-bit palette picks* (high 2 bits = left pixel, low 2 bits =
right pixel) rather than one flat fill: value ``8`` (``1000``) selects palette
2 (grey) for the left pixel but palette 0 (transparent) for the right one —
half a shadow. The dot's own value ``5`` (``0101``) picks palette 1 (white)
for *both* pixels, which is why the dot itself always renders as a solid
square while the shadow next to it looked hollow. Fix: use value ``0xA``
(``1010`` — palette 2 for both pixels) so the shadow fills solid grey across
its full width, matching the dot's own width instead of only half of it.

Issue #138 second follow-up (reporter's third screenshot, comparing to a
reference render): misdiagnosed at the time as the dot's own ink being one
pixel narrow. The fix turned nibble 37/41 (byte 18/20's high nibble) from
grey (``8`` = ``1000``) to white (``4`` = ``0100``). That nibble is column 2
of the local 4-column grid (the dot's own ink is column 3, nibbles 36/40) —
i.e. it sits to the dot's *left*, not its right, and it was never part of the
dot: it is the real « N » letter's own right-edge antialiasing column, grey in
every row 4-11 including rows 9-10 where the dot overlaps it. Turning it white
only in rows 9-10 broke that column's continuity, which is what the next
follow-up's "bottom of the N is wrong" report was actually showing.

Issue #138 third follow-up (reporter: the grey pixels turned white were fine
as they were; add three grey pixels to the right of the dot's white pixels
instead; the bottom of the N is now wrong): reverts the second follow-up's
mistake and, separately, closes the one remaining transparent gap in that
area. Nibble 37/41 goes back to having a grey (not transparent) *left*
sub-pixel — restoring the « N »'s antialiasing column across rows 9-11 and
fixing the "bottom of N" regression — and its previously-transparent *right*
sub-pixel (immediately beside the dot's own white column) also becomes grey:
value ``8`` (``1000``, grey+transparent) → ``0xA`` (``1010``, grey+grey).
The same right sub-pixel was already transparent (not grey) one row down too
— nibble 45 (byte 22's high nibble, row 11) goes from ``8`` to ``0xA`` for the
same reason, so the antialiasing column is solid grey, gap-free, all the way
from row 4 through row 11. Three cells flip from transparent to grey in total
(nibble 37's right sub-pixel, nibble 41's right sub-pixel, nibble 45's right
sub-pixel) — the three new grey pixels the reporter asked for — while the
dot's own white ink (nibbles 36/40) and its shadow (nibble 44) are untouched.

The patch is strict: the 32 bytes at ``0x1ECFA0`` must byte-match the known « Lv »
ligature, the shadow-less « N. » (#104 before-fix), the row-12-overflow « N. »
(#104 after-fix / #138 before-fix), the in-bounds-but-half-shadow « N. » (#138
fix), the full-shadow-but-narrow-dot « N. » (#138 second follow-up
before-fix), the mis-widened-dot « N. » (#138 third follow-up before-fix), or
the already-patched « N. »; anything else is reported and skipped rather than
corrupted.

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
# empty right column (nibbles 36/40 = local col 3, rows 9-10), value 5 = white,
# with its 3rd row (row 11, nibble 44) turned into the grey drop-shadow — value
# 0xA (both sub-pixels = palette 2/grey), not 0x8 (left sub-pixel grey, right
# sub-pixel transparent — a half-strength shadow, issue #138 follow-up) — so
# shadow + dot stay within rows 4-11 and the shadow is as solid/full-width as
# the dot's own white ink, in every UI context that reads this glyph. The real
# « N » letter's own antialiasing column (nibbles 37/41/45, local col 2, rows
# 9-11 — immediately left of the dot) is fully grey (0xA, both sub-pixels),
# not just its left sub-pixel (0x8, issue #138 third follow-up) — closing the
# gap beside the dot without touching the dot's own ink or shadow.
NEW_ND_GLYPH = bytes.fromhex(
    "0000c0ffc0ffc0ff806d8059805980658065a569a56daaaec0ff000000000000"
)

# Issue #138's own fix: shadow value 0x8 (nibble 44) — only the left of its two
# sub-pixels is grey, the right one is transparent, so the shadow rendered as a
# thin/incomplete sliver instead of a full grey square (reported as "manque des
# pixels gris" on the same issue after it was first closed). Accept it as a
# re-patchable state so an already-built ROM converges without a full rebuild —
# it differs from NEW_ND_GLYPH in byte 22 (0x88 vs 0x8A) and, since it predates
# the second follow-up's dot-widening, in bytes 18/20 too (0x85 vs 0x45).
OLD_ND_GLYPH_HALF_SHADOW = bytes.fromhex(
    "0000c0ffc0ffc0ff806d80598059806580658569856d88aec0ff000000000000"
)

# Issue #138 second follow-up's before-fix state: the row-11 shadow is already
# full-width (0xA), but the dot's own white ink (nibble 36/40) is only 2 pixels
# wide — one pixel narrower than that shadow and than the glyph's own
# antialiasing column beside it. Accept it as a re-patchable state so an
# already-built ROM converges without a full rebuild — it differs from
# NEW_ND_GLYPH only in bytes 18/20 (0x85 vs 0x45).
OLD_ND_GLYPH_NARROW_DOT = bytes.fromhex(
    "0000c0ffc0ffc0ff806d80598059806580658569856d8aaec0ff000000000000"
)

# Previous « N. » glyph shipped without the dot's drop-shadow (issue #104). Accept
# it as a re-patchable state so an already-built ROM converges without a full
# rebuild — it differs from NEW_ND_GLYPH in byte 22 (0x85 vs 0x8A) and byte 24
# (0xC0, same as NEW_ND_GLYPH here since neither carries a row-12 shadow).
OLD_ND_GLYPH_NOSHADOW = bytes.fromhex(
    "0000c0ffc0ffc0ff806d80598059806580658569856d85aec0ff000000000000"
)

# Issue #104's fix: 3-row dot (rows 9-11) + shadow at row 12 (nibble 48 = byte 24
# low nibble, 0xC0 → 0xC8). Renders correctly in the party list but the row-12
# shadow overflows the in-battle level-up box's border strip (issue #138). Accept
# it as a re-patchable state so already-built ROMs converge without a full rebuild.
OLD_ND_GLYPH_ROW12_OVERFLOW = bytes.fromhex(
    "0000c0ffc0ffc0ff806d80598059806580658569856d85aec8ff000000000000"
)

# Issue #138 second follow-up's own fix, now known to be wrong: it turned nibble
# 37/41 (byte 18/20's high nibble) white (0x4), thinking it widened the dot's own
# ink. That nibble is actually local col 2 — the real « N » letter's own
# antialiasing column, immediately *left* of the dot (col 3), grey in every row
# 4-11 — so turning it white only in rows 9-10 broke that column's continuity
# instead of widening anything (issue #138 third follow-up: "the grey pixels you
# turned white were fine; now the bottom of the N is wrong"). Accept it as a
# re-patchable state so an already-built ROM converges without a full rebuild —
# it differs from NEW_ND_GLYPH in bytes 18/20 (0x45 vs 0xA5) and byte 22 (0x8A vs
# 0xAA, since it predates the third follow-up's gap-closing fix too).
OLD_ND_GLYPH_MISWIDENED_DOT = bytes.fromhex(
    "0000c0ffc0ffc0ff806d80598059806580654569456d8aaec0ff000000000000"
)


def apply_patch(rom_path: Path) -> int:
    rom = bytearray(rom_path.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {rom_path}")

    current = bytes(rom[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE])

    if current == NEW_ND_GLYPH:
        print("  party level label (0x1ECFA0): already « N. » (full shadow, gap-free antialiasing) — no change")
        return 0

    known_old = (
        OLD_LV_GLYPH,
        OLD_ND_GLYPH_NOSHADOW,
        OLD_ND_GLYPH_ROW12_OVERFLOW,
        OLD_ND_GLYPH_HALF_SHADOW,
        OLD_ND_GLYPH_NARROW_DOT,
        OLD_ND_GLYPH_MISWIDENED_DOT,
    )
    if current not in known_old:
        print(
            f"  WARN party level label: glyph at 0x{LV_GLYPH_OFFSET:07X} matches "
            f"neither « Lv », the shadow-less « N. », the row-12-overflow « N. », "
            f"the half-shadow « N. », the narrow-dot « N. », the mis-widened-dot "
            f"« N. », nor the already-patched « N. » — skip\n"
            f"       got {current.hex()}",
            file=sys.stderr,
        )
        return 0

    if current == OLD_LV_GLYPH:
        was = "« Lv »"
    elif current == OLD_ND_GLYPH_NOSHADOW:
        was = "« N. » (no shadow)"
    elif current == OLD_ND_GLYPH_ROW12_OVERFLOW:
        was = "« N. » (shadow overflowing box border, issue #138)"
    elif current == OLD_ND_GLYPH_HALF_SHADOW:
        was = "« N. » (half shadow, issue #138 follow-up)"
    elif current == OLD_ND_GLYPH_NARROW_DOT:
        was = "« N. » (full shadow, narrow dot, issue #138 second follow-up)"
    else:
        was = "« N. » (antialiasing column mis-widened white, issue #138 third follow-up)"
    rom[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE] = NEW_ND_GLYPH
    rom_path.write_bytes(rom)
    print(f"  party level label (0x1ECFA0): {was} → « N. » (full shadow, gap-free antialiasing)")
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
