"""Guard issue #170's exact two-line text through the live PC-menu pointer."""

from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder


pytestmark = pytest.mark.rom

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FR_ROM = PROJECT_ROOT / "output/roms/GenedRom-fr.gba"
WITHDRAW_DESCRIPTION_POINTER = 0x3CDA34
WITHDRAW_DESCRIPTION_OFFSET = 0x4185AD


def test_pc_withdraw_description_is_revised_in_built_rom() -> None:
    rom = FR_ROM.read_bytes()
    address = int.from_bytes(
        rom[
            WITHDRAW_DESCRIPTION_POINTER : WITHDRAW_DESCRIPTION_POINTER + 4
        ],
        "little",
    )
    offset = address - 0x08000000
    terminator = rom.index(0xFF, offset)

    assert offset == WITHDRAW_DESCRIPTION_OFFSET
    assert terminator == 0x4185E0
    assert TextDecoder.decode_pokemon(rom[offset : terminator + 1]) == (
        "Intégrer dans l'équipe des Pokémon\npris des boîtes."
    )
