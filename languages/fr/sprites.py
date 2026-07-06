"""Registry of named UI sprites for the extract/insert BMP tool (ticket F-108).

A sprite may live at several byte-identical LZ77 block offsets in the ROM
(the CFRU engine keeps duplicate copies of some UI tile sheets for different
screens/palettes) — ``extract_sprite.py``/``insert_sprite.py`` target one
block at a time via ``--block-index``, or every block when it is omitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class SpriteDef:
    blocks: Tuple[int, ...]
    tiles_wide: int
    tiles_tall: int
    # True (default): block is LZ77-compressed (magic byte 0x10), recompressed
    # on insert. False: block is a flat run of raw/uncompressed 4bpp tiles at
    # a fixed size — used for small OBJ tilesets the engine DMAs directly
    # rather than decompressing (e.g. the naming-keyboard help panel).
    compressed: bool = True


SPRITES: dict[str, SpriteDef] = {
    # 8 status-condition badges (POI/PAR/SOM/GEL/BRU/…/KO), 4 tiles wide x 1
    # tile tall each, stacked into one 32x64 sheet. Same offsets as
    # languages/fr/patches/status_badges.py's BADGE_BLOCKS.
    "status_badges": SpriteDef(
        blocks=(0x0B1E11C, 0x0B1E280, 0x00E82EA0, 0x00E9BF48),
        tiles_wide=4,
        tiles_tall=8,
    ),
    # Player/rival naming keyboard's right-side help panel (ticket F-109):
    # blank shift-state swatch + "SELECT (>", "BACK"/"B BUTTON"/"OK"/"START",
    # then the 3 alternate shift-state labels ("UPPER"/"lower"/"others")
    # DMA'd into that swatch at runtime. Stored as raw uncompressed OBJ
    # tiles (not LZ77) — located via mGBA OAM/VRAM probing, see
    # scripts/probe_naming_sprites.mts and scripts/probe_sync_label.mts.
    "selection": SpriteDef(
        blocks=(0x00E985D8,),
        tiles_wide=5,
        tiles_tall=13,
        compressed=False,
    ),
    # START-menu icon-reorder hint bar (GitHub issue #43): the SELECT keycap +
    # the word "Move" shown at the bottom of the custom START menu. It is NOT
    # string-table text — it is a 15-tile LZ77 tile-strip (120x8) baked
    # pixel-for-pixel into the ROM, referenced from the menu code at 0x0A0C210:
    #   tiles 0-7  : window/frame border pieces
    #   tiles 8-11 : the "SELECT" keycap
    #   tiles 12-14: the word "Move"  (redraw these to "Dépl." by hand)
    # Fill = palette index 15 (light), bevel/outline = 14 (dark), the bar's
    # vertical gradient background = indices 1-4. Extract to a .bmp with
    # extract_sprite.py, redraw "Move", re-inject with insert_sprite.py. An
    # earlier attempt to redraw these tiles procedurally glitched the menu, so
    # the hand-edited-BMP path is the supported way to translate this sprite.
    "start_menu_move_hint": SpriteDef(
        blocks=(0x0B1BBE0,),
        tiles_wide=15,
        tiles_tall=1,
    ),
}
