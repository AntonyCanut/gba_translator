"""Protège les libellés de temps des écrans Carte Dresseur et sauvegarde."""

from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder


pytestmark = pytest.mark.rom

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FR_ROM = PROJECT_ROOT / "output/roms/GenedRom-fr.gba"
ROM_BASE = 0x08000000
TRAINER_CARD_TIME_POINTER = 0xCF34
SAVE_SCREEN_TIME_POINTERS = (0x6FE80, 0x1EB6220)
EXPECTED_PLAY_TIME_BYTES = bytes.fromhex("BE E9 E6 1B D9 00 DE D9 E9 FF")


def _decode_pointer(rom: bytes, pointer_offset: int) -> str:
    address = int.from_bytes(rom[pointer_offset : pointer_offset + 4], "little")
    offset = address - ROM_BASE
    terminator = rom.index(0xFF, offset)
    return TextDecoder.decode_pokemon(rom[offset : terminator + 1])


def test_trainer_card_uses_canonical_play_time_label() -> None:
    rom = FR_ROM.read_bytes()

    assert _decode_pointer(rom, TRAINER_CARD_TIME_POINTER) == "Durée jeu"


def test_trainer_card_label_has_exact_bytes_and_terminator() -> None:
    rom = FR_ROM.read_bytes()
    target = (
        int.from_bytes(
            rom[TRAINER_CARD_TIME_POINTER : TRAINER_CARD_TIME_POINTER + 4],
            "little",
        )
        - ROM_BASE
    )

    assert rom[target : target + len(EXPECTED_PLAY_TIME_BYTES)] == EXPECTED_PLAY_TIME_BYTES


def test_save_screen_keeps_short_time_label() -> None:
    rom = FR_ROM.read_bytes()

    assert {
        _decode_pointer(rom, pointer_offset)
        for pointer_offset in SAVE_SCREEN_TIME_POINTERS
    } == {"Temps"}
