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
instead; the bottom of the N is now wrong): reverted the second follow-up's
mistake (nibble 37/41 back to a grey *left* sub-pixel, restoring the « N »'s
antialiasing column and fixing the "bottom of N" regression) but *mis-read*
"to the right of the dot's white pixels" as "the right sub-pixel of this same
antialiasing column" (nibble 37/41/45's low 2 bits, local col 2) and turned
those grey too (``8`` → ``0xA``). That column (local col 2) is immediately
**left** of the dot's own ink (local col 3) — both of its sub-pixels sit to
the dot's left on screen, so this added grey on the wrong side of the dot
rather than the right, which the reporter confirmed in the next follow-up.

Issue #138 fourth follow-up (reporter: "so close! the grey pixels are on the
wrong side"): reverts the third follow-up's right-sub-pixel change (nibble
37/41/45 back to ``8`` — grey left sub-pixel, transparent right sub-pixel),
which is the only safe, glyph-internal fix available. The glyph is a fixed
8-physical-pixel-wide tile (4 local columns × 2 sub-pixels); the dot's own
ink already occupies the tile's last two physical columns (local col 3),
flush against its right edge, so there is no physical pixel column *inside
this glyph* to the dot's right — "right of the dot" would fall on the next
codepoint's own glyph (whatever follows « N. » on screen, e.g. a space),
which this ligature glyph patch cannot reach without editing a different,
shared codepoint used everywhere else in the font. This revert at least
removes the confirmed-wrong left-side placement; see the GitHub issue for
the pixel-grid raised with the reporter to pin down exactly what a
right-side accent would need to touch.

The patch is strict: the 32 bytes at ``0x1ECFA0`` must byte-match the known « Lv »
ligature, the shadow-less « N. » (#104 before-fix), the row-12-overflow « N. »
(#104 after-fix / #138 before-fix), the in-bounds-but-half-shadow « N. » (#138
fix), the mis-widened-dot « N. » (#138 second follow-up), the
wrong-side-shaded « N. » (#138 third follow-up), or the already-patched
« N. »; anything else is reported and skipped rather than corrupted.

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
# 9-11 — immediately left of the dot) keeps its left sub-pixel grey (0x8) and
# its right sub-pixel transparent, same as every other row of that column —
# issue #138 third follow-up made that right sub-pixel grey too (0xA), meaning
# to add shading beside the dot, but that sub-pixel sits to the dot's *left*,
# not its right (issue #138 fourth follow-up), so it's reverted here.
NEW_ND_GLYPH = bytes.fromhex(
    "0000c0ffc0ffc0ff806d80598059806580658569856d8aaec0ff000000000000"
)

# Issue #138's own fix: shadow value 0x8 (nibble 44) — only the left of its two
# sub-pixels is grey, the right one is transparent, so the shadow rendered as a
# thin/incomplete sliver instead of a full grey square (reported as "manque des
# pixels gris" on the same issue after it was first closed). Accept it as a
# re-patchable state so an already-built ROM converges without a full rebuild —
# it differs from NEW_ND_GLYPH only in byte 22 (0x88 vs 0x8A).
OLD_ND_GLYPH_HALF_SHADOW = bytes.fromhex(
    "0000c0ffc0ffc0ff806d80598059806580658569856d88aec0ff000000000000"
)

# Issue #138 third follow-up's own fix, now known to be wrong side: it made the
# « N » antialiasing column's right sub-pixel grey (nibbles 37/41/45, 0x8 ->
# 0xA) meaning to shade the dot's right, but that column sits to the dot's
# *left* (issue #138 fourth follow-up: "the grey pixels are on the wrong
# side"). Accept it as a re-patchable state so an already-built ROM converges
# without a full rebuild — it differs from NEW_ND_GLYPH in bytes 18/20/22
# (0xA5/0xA5/0xAA vs 0x85/0x85/0x8A).
OLD_ND_GLYPH_ANTIALIAS_WRONG_SIDE = bytes.fromhex(
    "0000c0ffc0ffc0ff806d8059805980658065a569a56daaaec0ff000000000000"
)

# Previous « N. » glyph shipped without the dot's drop-shadow (issue #104). Accept
# it as a re-patchable state so an already-built ROM converges without a full
# rebuild — it differs from NEW_ND_GLYPH only in byte 22 (0x85 vs 0x8A).
OLD_ND_GLYPH_NOSHADOW = bytes.fromhex(
    "0000c0ffc0ffc0ff806d80598059806580658569856d85aec0ff000000000000"
)

# Issue #104's fix: 3-row dot (rows 9-11) + shadow at row 12 (nibble 48 = byte 24
# low nibble, 0xC0 → 0xC8). Renders correctly in the party list but the row-12
# shadow overflows the in-battle level-up box's border strip (issue #138). Accept
# it as a re-patchable state so already-built ROMs converge without a full
# rebuild — it differs from NEW_ND_GLYPH in byte 22 (0x85 vs 0x8A) and byte 24
# (0xC8 vs 0xC0).
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
# it differs from NEW_ND_GLYPH only in bytes 18/20 (0x45 vs 0x85).
OLD_ND_GLYPH_MISWIDENED_DOT = bytes.fromhex(
    "0000c0ffc0ffc0ff806d80598059806580654569456d8aaec0ff000000000000"
)


def apply_patch(rom_path: Path) -> int:
    rom = bytearray(rom_path.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {rom_path}")

    current = bytes(rom[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE])

    if current == NEW_ND_GLYPH:
        print("  party level label (0x1ECFA0): already « N. » (full shadow, antialiasing column on the dot's left) — no change")
        return 0

    known_old = (
        OLD_LV_GLYPH,
        OLD_ND_GLYPH_NOSHADOW,
        OLD_ND_GLYPH_ROW12_OVERFLOW,
        OLD_ND_GLYPH_HALF_SHADOW,
        OLD_ND_GLYPH_MISWIDENED_DOT,
        OLD_ND_GLYPH_ANTIALIAS_WRONG_SIDE,
    )
    if current not in known_old:
        print(
            f"  WARN party level label: glyph at 0x{LV_GLYPH_OFFSET:07X} matches "
            f"neither « Lv », the shadow-less « N. », the row-12-overflow « N. », "
            f"the half-shadow « N. », the mis-widened-dot « N. », the wrong-side-shaded "
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
    elif current == OLD_ND_GLYPH_MISWIDENED_DOT:
        was = "« N. » (antialiasing column mis-widened white, issue #138 third follow-up)"
    else:
        was = "« N. » (antialiasing column shaded on the dot's wrong side, issue #138 fourth follow-up)"
    rom[LV_GLYPH_OFFSET:LV_GLYPH_OFFSET + GLYPH_SIZE] = NEW_ND_GLYPH
    rom_path.write_bytes(rom)
    print(f"  party level label (0x1ECFA0): {was} → « N. » (full shadow, antialiasing column on the dot's left)")
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
