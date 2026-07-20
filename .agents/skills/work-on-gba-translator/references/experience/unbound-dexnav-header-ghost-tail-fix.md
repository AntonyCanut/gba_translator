---
name: unbound-dexnav-header-ghost-tail-fix
description: DexNav column-header graphic patch left a ghost duplicate of the original English text below shortened DE/FR labels (issue
metadata:
  node_type: memory
  type: project
  originSessionId: 341cc47f-8840-414e-82b0-56a0b4724461
---

The DexNav screen's 4 column-header graphics (`languages/<lang>/patches/dexnav_headers.py`
in `gba_translator`) only ever cleared the header's *own* tile-row (rows 2-7 of
`first_tile..first_tile+ntiles`) before drawing the translated label. But 3 of the 4
English source headers are two words tall ("SEARCH"/"LEVEL", "HIDDEN"/"ABILITY",
"HELD"/"ITEMS" — only "METHOD" is single-word), and their letter pixels spill 1-2px into
rows 0-1 of the tile-map row **directly below**. Since the translated label is a single
shortened line (e.g. DE "SUCHLEVEL", FR "NIVEAU RECH"), that spillover from the original
English second line survives untouched and renders as a pale ghost duplicate under the new
text — exactly what issue #90's screenshot showed. **This bug existed identically in both
the DE and FR ports** (same tile ranges, same `_stamp_text`) despite FR's port being
previously reported clean (see [[unbound-dexnav-labels-mixed-text-graphics]] — F-71 was
about class 1 vs class 2 labels, not this).

Root cause found empirically, not by reasoning about the source art: decompressed the
tileset (0x00B14FA0) + tilemap (0x00B15438) directly from the built ROM with a small PIL
script and rendered the 32x20 grid — pixel-identical to the reported screenshot. Reading
the tilemap at the header's own columns (map row 6/9/12/15) then reading the same columns
at map row+1 (7/10/13/16) gives the exact "ghost tile" IDs — some rows share physical tile
IDs between adjacent headers' ghost ranges (e.g. tile 67 belongs to both METHODE's and
VERST.FAEH's row-below at different columns; tile 47 similarly shared by SUCHLEVEL/ITEMS) —
this falls out naturally from the tile ranges, no special-casing needed.

**Fix**: added `GHOST_TILES` (maps each header's `first_tile` → `range` of tile IDs in the
row below) and `_clear_ghost_tail()` to `languages/de/patches/dexnav_headers.py` (FR got an
independent copy; IT already imports `_stamp_text` etc. from DE, so it also imports
`GHOST_TILES`/`_clear_ghost_tail` for free). The clear is conditional per-pixel: only erase
a rows-0-1 pixel if it does NOT continue into row 2 of the same tile — this is what
distinguishes genuine letter-ghost (isolated to the top 1-2 rows) from legitimate
background art like tile 49's rounded-corner decoration (uses the same fill colour across
all 8 rows, a continuous shape that must survive). Verified via direct pixel-render
before/after in `/tmp` (not just the tileset-hex byte-diff the earlier investigation agent
used — that check alone is insufficient, since a `_stamp_text`-only render is internally
consistent with itself even though the underlying algorithm never touches the ghost tile
range at all).

**Also fixed same-issue**: `combined_de.txt` `0xA439B6` was "Erde" (Earth/ground), changed
to "Land" to match the German localization convention for the DexNav ground-habitat tab
(sibling of `0xA439B0: Wasser`).

**How to apply**: if a future language port (IT/indie/etc.) reports a similar "ghost text"
under a DexNav header, the same `GHOST_TILES` mechanism already covers it via the DE import
— just confirm the port's `apply_patches` calls `_clear_ghost_tail(tiles,
GHOST_TILES[first_tile])` after `_stamp_text`. If a *new* baked-graphic header/label bug
ever shows partial ghosting like this, the diagnostic method (decompress tileset+tilemap
directly from the ROM, render to PNG, diff row-below tiles) is much faster and more
reliable than reasoning from the tileset hex fingerprint alone or guessing from a
screenshot.
