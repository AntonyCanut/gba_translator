"""Registry of named UI sprites for the indexed PNG/BMP extract/insert tool.

A sprite may live at several LZ77 block offsets in the ROM (the CFRU engine
keeps copies of some UI tile sheets for different screens/palettes).
``extract_sprite.py --all-blocks`` creates one indexed image per copy and
``insert_sprite.py --all-blocks`` consumes those same numbered files, so the
palette indices of one screen cannot corrupt another.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpriteDef:
    blocks: tuple[int, ...]
    tiles_wide: int
    tiles_tall: int
    # Profondeur des indices de palette stockés dans chaque tuile GBA.
    bits_per_pixel: int = 4
    # True (default): block is LZ77-compressed (magic byte 0x10), recompressed
    # on insert. False: block is a flat run of raw/uncompressed 4/8bpp tiles at
    # a fixed size — used for small OBJ tilesets the engine DMAs directly
    # rather than decompressing (e.g. the naming-keyboard help panel).
    compressed: bool = True
    # True for streams decompressed directly to VRAM. Status badges use the
    # compact standard stream accepted by their existing patch; VRAM-safe
    # output is three bytes larger and does not fit their fixed ROM slots.
    vram_safe: bool = True
    # Optional LZ77 tilemap paired one-for-one with ``blocks``. When present,
    # extraction reconstructs the mapped screen and insertion reverses that
    # composition instead of exposing a scrambled linear tilesheet.
    tilemaps: tuple[int, ...] = ()
    # Pointeurs ROM connus vers chaque planche, appariés à ``blocks``. Ils
    # permettent une relocalisation sûre si une recompression ne tient plus
    # dans le bloc d’origine.
    block_pointers: tuple[tuple[int, ...], ...] = ()
    # Pointeurs ROM connus vers chaque tilemap, appariés à ``blocks``. Ils
    # permettent une relocalisation sûre si une édition ne tient plus dans le
    # bloc LZ77 d’origine ; aucun scan aveugle de pointeurs n’est effectué.
    tilemap_pointers: tuple[tuple[int, ...], ...] = ()
    # Optional ROM offset of the sheet's 16/256-colour BGR555 palette. Only the
    # palette *indices* are re-injected, but embedding the real colours makes
    # the extracted image legible in an editor instead of a debug-coloured mess.
    palette: int | None = None
    # Optional first tile for a partial view into each block. Empty means tile
    # zero for every block. This keeps small editable labels independent from
    # the rest of a large shared tileset.
    start_tiles: tuple[int, ...] = ()
    # Optional physical capacities for compressed slots. Declaring them keeps
    # repeated edits safe when an earlier re-compression made a stream shorter.
    max_compressed_sizes: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        """Valide l'appariement des planches et tilemaps."""
        if self.bits_per_pixel not in (4, 8):
            raise ValueError("SpriteDef bits_per_pixel must be 4 or 8")
        if self.tilemaps and len(self.tilemaps) != len(self.blocks):
            raise ValueError("SpriteDef requires one tilemap per block")
        if self.block_pointers and len(self.block_pointers) != len(self.blocks):
            raise ValueError("SpriteDef requires pointer sets for every block")
        if self.tilemap_pointers and len(self.tilemap_pointers) != len(self.blocks):
            raise ValueError("SpriteDef requires pointer sets for every block")
        if self.tilemap_pointers and not self.tilemaps:
            raise ValueError("SpriteDef tilemap pointers require tilemaps")
        if self.start_tiles and len(self.start_tiles) != len(self.blocks):
            raise ValueError("SpriteDef requires one start tile per block")
        if (
            self.max_compressed_sizes
            and len(self.max_compressed_sizes) != len(self.blocks)
        ):
            raise ValueError("SpriteDef requires one compressed size per block")


SPRITES: dict[str, SpriteDef] = {
    # 8 status-condition badges (POI/PAR/SOM/GEL/BRU/…/KO), 4 tiles wide x 1
    # tile tall each, stacked into one 32x64 sheet. Same offsets as
    # languages/fr/patches/status_badges.py's BADGE_BLOCKS. The canonical
    # editable reference is languages/fr/sprites/status_badges.bmp; the PNG
    # is a synchronized preview for editors that prefer that format.
    "status_badges": SpriteDef(
        blocks=(0x0B1E11C, 0x0B1E280, 0x00E82EA0, 0x00E9BF48),
        tiles_wide=4,
        tiles_tall=8,
        vram_safe=False,
    ),
    # Type badges (issue #156): separate raw 16-tile-wide sheets for the
    # summary screen and the battle move menu. Their useful heights differ,
    # as does the CFRU Fairy badge's tile offset. Keeping each complete useful
    # rectangle preserves the tiles shared by neighbouring 32x24 badges.
    #
    #   for name in type_icons_summary type_icons_battle; do
    #       python3 scripts/extract_sprite.py \
    #           --rom output/roms/GenedRom-fr.gba --lang fr \
    #           --sprite "$name" -o "languages/fr/sprites/$name.png"
    #   done
    "type_icons_summary": SpriteDef(
        blocks=(0x00B1EC64,),
        tiles_wide=16,
        tiles_tall=19,
        compressed=False,
    ),
    "type_icons_battle": SpriteDef(
        blocks=(0x00961A00,),
        tiles_wide=16,
        tiles_tall=13,
        compressed=False,
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
    # The block is decompressed directly into VRAM: its LZ77 stream must avoid
    # odd-distance overlapping references.  The generic sprite inserter uses
    # VRAM-safe compression for that reason; a normal Python-valid LZ77 stream
    # otherwise corrupts every tile after the first unsupported reference.
    "start_menu_move_hint": SpriteDef(
        blocks=(0x0B1BBE0,),
        tiles_wide=15,
        tiles_tall=1,
    ),
    # Cube pocket footer (GitHub issue #140): compressed BG tiles loaded at
    # charblock 3.  The first 52 tiles form a 13x4 editable sheet containing
    # the baked ``START Sort`` hint; the final 10 tiles in the same LZ77 block
    # are intentionally preserved by ``insert_block``.
    "cube_sort_hint": SpriteDef(
        blocks=(0x00EF1B68,),
        tiles_wide=13,
        tiles_tall=4,
    ),
    # Exterior Pokémon Mart sign (GitHub issue #152): the four-letter word
    # has three active tileset copies.  Two use tiles 225-226 and the primary
    # overworld tileset uses 413-414.  Only those 16x8 windows are exposed, so
    # every neighbouring tile keeps its original indices and palette style.
    "pokemon_mart_sign": SpriteDef(
        blocks=(0x007559B8, 0x00B89D5C, 0x00CF91A0),
        start_tiles=(225, 225, 413),
        max_compressed_sizes=(10_452, 10_531, 11_604),
        tiles_wide=2,
        tiles_tall=1,
        palette=0x00EA1BC8,
    ),
    # Trainer Card front and back (GitHub issue #148): the headings
    # "TRAINER CARD" and "LEAGUE BADGES" are baked into separate LZ77
    # tilesheets. Their 32x20 tilemaps rebuild a directly editable full-screen
    # PNG while the mapped inserter preserves shared/flipped source tiles.
    "trainer_card_front": SpriteDef(
        blocks=(0x01FDA2BC,),
        tilemaps=(0x01FDA820,),
        block_pointers=((0x01ED8AA4,),),
        tilemap_pointers=((0x01ED8AA8,),),
        tiles_wide=32,
        tiles_tall=20,
    ),
    "trainer_card_back": SpriteDef(
        blocks=(0x01FDAA4C,),
        tilemaps=(0x01FDB2AC,),
        tilemap_pointers=((0x01ED8AB8,),),
        tiles_wide=32,
        tiles_tall=20,
    ),
    # Écran titre Unbound (GitHub issue #155) : BG1 8 bpp complet. La planche,
    # la tilemap et la palette reconstruisent un PNG 256 × 160 où le dessin
    # « PRESS START » peut être retouché directement. L’asset anglais n’est pas
    # injecté par build-fr tant qu’un dessin français n’a pas été validé.
    "title_screen": SpriteDef(
        blocks=(0x01FD4854,),
        tilemaps=(0x01FD6514,),
        tiles_wide=32,
        tiles_tall=20,
        bits_per_pixel=8,
        palette=0x01FD699C,
    ),
    # Word-image tileset of the Pokémon summary screen (GitHub issue #145):
    # 512 tiles, 16 wide, holding every baked label of the « Infos » and
    # « Capacités » pages — N° / NOM / TYPE / DO / N°ID / OBJET on the left,
    # ATTAQUE / DEFENSE / ATT SPE. / DEF SPE. / VITESSE / EXP. in the stat
    # column, POUV. / PRECISION on the move panel, plus the grey « PV » oval.
    # None of it is text, so no translation pass reaches it.
    #
    # ** languages/fr/sprites/summary_stat_labels.png is the source of truth **
    # for the whole block. build-fr inserts it after hp_labels.py and
    # summary_stat_labels.py, which redraw the « PV » oval and the four stat
    # capsules programmatically; the drawing carries their output too, so it
    # wins without losing anything. tests/test_summary_sheet_fr.py locks that
    # agreement — if you edit one side only, it fails.
    #
    # To retouch: export the sheet, edit the PNG keeping its 16-colour indexed
    # palette (1 = letters, 7 = capsule, 0xA = panel background), and commit it.
    #
    #   python3 scripts/extract_sprite.py --rom output/roms/GenedRom-fr.gba \
    #       --lang fr --sprite summary_stat_labels \
    #       -o languages/fr/sprites/summary_stat_labels.png
    "summary_stat_labels": SpriteDef(
        blocks=(0x00E9A460,),
        tiles_wide=16,
        tiles_tall=32,
        palette=0x00E9B310,
    ),
    # Libellés graphiques des boîtes PC (issue #163) : "PKMN DATA", "PARTY
    # POKéMON" et "CLOSE BOX" ne sont pas des chaînes CFRU. Cette fenêtre de
    # 144 tuiles, avec sa palette propre, est extraite telle quelle pour une
    # retouche manuelle ; elle n'est pas injectée automatiquement par build-fr.
    "pc_box_labels": SpriteDef(
        blocks=(0x00E9C438,),
        block_pointers=((0x0008F034,),),
        tiles_wide=16,
        tiles_tall=9,
        palette=0x003CE5DC,
    ),
}
