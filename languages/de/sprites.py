"""Registre des écrans graphiques éditables propres à la version allemande."""

from __future__ import annotations

from languages.fr.sprites import SpriteDef


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
