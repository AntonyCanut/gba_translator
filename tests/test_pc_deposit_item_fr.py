"""Régression du libellé « Déposer objet » dans les menus PC."""

import struct
from pathlib import Path

import pytest

pytestmark = pytest.mark.rom

from src.core.text_codec import TextEncoder


FR_ROM = Path("output/roms/GenedRom-fr.gba")
GBA_ROM_BASE = 0x08000000
DEPOSIT_ITEM_POINTER_OFFSETS = (0x0010B9D8, 0x00402210)
EXPECTED_LABEL = "Déposer objet"


def _read_terminated_string(rom: bytes, pointer_offset: int) -> bytes:
    """Retourne la chaîne terminée ciblée par un pointeur ROM."""
    target = struct.unpack_from("<I", rom, pointer_offset)[0] - GBA_ROM_BASE
    terminator = rom.find(bytes([TextEncoder.POKEMON_TERMINATOR]), target)
    assert terminator >= target, (
        f"chaîne non terminée ciblée par le pointeur 0x{pointer_offset:X}"
    )
    return rom[target : terminator + 1]


@pytest.mark.parametrize("pointer_offset", DEPOSIT_ITEM_POINTER_OFFSETS)
@pytest.mark.rom
def test_pc_deposit_item_label_keeps_its_initial_d(pointer_offset: int) -> None:
    """Chaque menu PC doit afficher le libellé complet et isolé."""
    rom = FR_ROM.read_bytes()
    expected = TextEncoder.encode_pokemon(EXPECTED_LABEL)

    actual = _read_terminated_string(rom, pointer_offset)

    assert actual == expected
