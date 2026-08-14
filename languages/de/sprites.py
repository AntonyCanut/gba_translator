"""Registre des écrans graphiques éditables propres à la version allemande."""

from __future__ import annotations

from languages.fr.sprites import SPRITES as REFERENCE_SPRITES
from languages.fr.sprites import SpriteDef

_MENU_SPRITES = (
    "cube_sort_hint",
    "pc_box_labels",
    "pokemon_mart_sign",
    "selection",
    "start_menu_move_hint",
)

_BATTLE_SUMMARY_REFERENCE_SPRITES = (
    "status_badges",
    "type_icons_summary",
    "type_icons_battle",
    "summary_stat_labels",
)

SPRITES: dict[str, SpriteDef] = {
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
    "title_screen": SpriteDef(
        blocks=(0x01FD4854,),
        tilemaps=(0x01FD6514,),
        block_pointers=((0x01ED7C7C, 0x01ED7EC0),),
        tilemap_pointers=((0x01ED7C84, 0x01ED7EC8),),
        tiles_wide=32,
        tiles_tall=20,
        bits_per_pixel=8,
        palette=0x01FD699C,
    ),
}

# La géométrie, les pointeurs et les budgets appartiennent à la ROM Unbound et
# sont identiques entre langues. Seules les images dans languages/de/sprites
# sont spécifiques à l'allemand.
SPRITES.update({name: REFERENCE_SPRITES[name] for name in _MENU_SPRITES})
SPRITES.update(
    {name: REFERENCE_SPRITES[name] for name in _BATTLE_SUMMARY_REFERENCE_SPRITES}
)

# Fenêtres graphiques absentes du registre FR : les générateurs DE existants
# les redessinent à ces offsets exacts. Le patch raster final les réinjecte
# depuis les PNG versionnés, après les réparations LZ77 et ces générateurs.
SPRITES.update(
    {
        "party_kp_label": SpriteDef(
            blocks=(0x008001D0,),
            tiles_wide=8,
            tiles_tall=10,
            vram_safe=False,
        ),
        "summary_kp_bar": SpriteDef(
            blocks=(0x00E9B4B8,),
            tiles_wide=12,
            tiles_tall=1,
            vram_safe=False,
            max_compressed_sizes=(192,),
        ),
        "battle_kp_labels": SpriteDef(
            blocks=(0x00D1F604, 0x00EEF0AC, 0x00EEF380, 0x00EEF688),
            tiles_wide=2,
            tiles_tall=1,
            vram_safe=False,
            start_tiles=(19, 20, 19, 19),
        ),
        "battle_kp_elements": SpriteDef(
            blocks=(0x00D11BC4, 0x00D11BE4),
            tiles_wide=1,
            tiles_tall=1,
            compressed=False,
        ),
        "battle_status_badges": SpriteDef(
            blocks=(0x00D11E64, 0x00D124A4, 0x00D12684, 0x00D12864),
            tiles_wide=3,
            tiles_tall=5,
            compressed=False,
        ),
        # Le marqueur officiel allemand reste la ligature originale « Lv ».
        # Cette tuile de police brute est partagée par l'équipe, le résumé et
        # les healthboxes ; la versionner empêche une fuite du glyphe FR « N. ».
        "level_marker": SpriteDef(
            blocks=(0x001ECFA0,),
            tiles_wide=1,
            tiles_tall=1,
            compressed=False,
        ),
    }
)
