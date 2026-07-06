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


SPRITES: dict[str, SpriteDef] = {
    # 8 status-condition badges (POI/PAR/SOM/GEL/BRU/…/KO), 4 tiles wide x 1
    # tile tall each, stacked into one 32x64 sheet. Same offsets as
    # languages/fr/patches/status_badges.py's BADGE_BLOCKS.
    "status_badges": SpriteDef(
        blocks=(0x0B1E11C, 0x0B1E280, 0x00E82EA0, 0x00E9BF48),
        tiles_wide=4,
        tiles_tall=8,
    ),
}
