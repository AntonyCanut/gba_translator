"""E2E: Italian item and move descriptions decode correctly in the built ROM.

Mirrors ``tests/e2e/fr/test_item_descriptions.py`` — decode the live CFRU
pointers (items table 0x876074, stride 44; move-description table 0x99F190,
mirroring ``src.core.moves.MOVE_DESCRIPTION_TABLE``) instead of trusting raw
combined_it.txt offsets, since the generic pipeline can relocate text.

Only entries verified to already carry clean Italian are asserted here
(Fresh Water / "Acqua Fresca", and moves Pound/Tackle/Bite/Rock Throw). A
meaningful fraction of the items table still ships stale French leftovers
baked into ``input/roms/englishrom.gba`` itself (tracked separately — see
follow-up ticket "~18% of item descriptions ... ship French leftover text");
this file intentionally does not assert on those broken entries.
"""

from __future__ import annotations

import struct
from typing import Optional

from src.text.charmap_data import BYTE_TO_CHAR

ITEMS_TABLE = 0x876074
ITEM_STRIDE = 44
ITEM_NAME_FIELD = 14
ITEM_DESC_PTR_OFFSET = 0x14

MOVE_DESCRIPTION_TABLE = 0x99F190

GBA_BASE = 0x08000000

ITEM_FRESH_WATER = 0x23

MOVE_POUND = 1
MOVE_TACKLE = 33
MOVE_BITE = 44
MOVE_ROCK_THROW = 88


def _follow_ptr(rom: bytes, ptr_offset: int) -> Optional[int]:
    ptr = struct.unpack_from("<I", rom, ptr_offset)[0]
    if ptr < GBA_BASE:
        return None
    return ptr - GBA_BASE


def _decode(rom: bytes, offset: int, max_len: int = 300) -> str:
    result = []
    i = offset
    limit = min(offset + max_len, len(rom))
    while i < limit:
        b = rom[i]
        if b == 0xFF:
            break
        if b == 0xFE:
            result.append("\n")
            i += 1
        elif b in (0xFC, 0xFD):
            i += 2
        elif b in BYTE_TO_CHAR:
            result.append(BYTE_TO_CHAR[b])
            i += 1
        else:
            i += 1
    return "".join(result)


def _item_name(rom: bytes, item_id: int) -> str:
    offset = ITEMS_TABLE + item_id * ITEM_STRIDE
    return _decode(rom, offset, max_len=ITEM_NAME_FIELD)


def _item_description(rom: bytes, item_id: int) -> Optional[str]:
    offset = ITEMS_TABLE + item_id * ITEM_STRIDE + ITEM_DESC_PTR_OFFSET
    desc_offset = _follow_ptr(rom, offset)
    if desc_offset is None:
        return None
    return _decode(rom, desc_offset)


def _move_description(rom: bytes, move_id: int) -> Optional[str]:
    offset = MOVE_DESCRIPTION_TABLE + move_id * 4
    desc_offset = _follow_ptr(rom, offset)
    if desc_offset is None:
        return None
    return _decode(rom, desc_offset)


class TestItemDescriptions:
    """Verify a known-clean item's name and description via live ROM pointers."""

    def test_fresh_water_name_is_italian(self, it_rom_path):
        rom = it_rom_path.read_bytes()
        name = _item_name(rom, ITEM_FRESH_WATER)
        assert name == "Acqua Fresca", f"Fresh Water name unexpected: {name!r}"

    def test_fresh_water_description_is_italian(self, it_rom_path):
        rom = it_rom_path.read_bytes()
        text = _item_description(rom, ITEM_FRESH_WATER)
        assert text is not None, "Fresh Water: null/invalid description pointer"
        assert "PS" in text, f"expected Italian 'PS' (Punti Salute) in {text!r}"
        assert "PV" not in text, f"French 'PV' residue found: {text!r}"
        assert "HP" not in text, f"English 'HP' residue found: {text!r}"


class TestMoveDescriptions:
    """Verify known-clean move descriptions via the live gMoveDescriptionPointers table."""

    CASES = [
        (MOVE_POUND, "un attacco fisico"),
        (MOVE_TACKLE, "un attacco fisico"),
        (MOVE_BITE, "l'utente morde"),
        (MOVE_ROCK_THROW, "il bersaglio viene"),
    ]

    def test_move_descriptions_are_italian(self, it_rom_path):
        rom = it_rom_path.read_bytes()
        for move_id, expected_prefix_lower in self.CASES:
            text = _move_description(rom, move_id)
            assert text is not None, f"move {move_id}: null/invalid description pointer"
            normalized = text.replace("\n", " ").lower()
            assert normalized.startswith(expected_prefix_lower), (
                f"move {move_id} description not the expected Italian text: {text!r}"
            )

    def test_move_descriptions_have_no_french_pronoun_residue(self, it_rom_path):
        rom = it_rom_path.read_bytes()
        for move_id, _ in self.CASES:
            text = _move_description(rom, move_id)
            normalized = text.replace("\n", " ")
            assert " le " not in normalized and "L'ennemi" not in normalized, (
                f"move {move_id} description carries French residue: {text!r}"
            )
