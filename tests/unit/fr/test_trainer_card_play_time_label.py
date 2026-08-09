"""Guard issue #176's play-time label through the live Trainer Card pointers."""

from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder


pytestmark = pytest.mark.rom

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FR_ROM = PROJECT_ROOT / "output/roms/GenedRom-fr.gba"
ROM_BASE = 0x08000000
TRAINER_CARD_TIME_POINTERS = (0x6FE80, 0x1EB6220)
SAVE_SUMMARY_TIME_POINTER = 0xCF34


def _decode_pointer(rom: bytes, pointer_offset: int) -> str:
    address = int.from_bytes(rom[pointer_offset : pointer_offset + 4], "little")
    offset = address - ROM_BASE
    terminator = rom.index(0xFF, offset)
    return TextDecoder.decode_pokemon(rom[offset : terminator + 1])


def test_trainer_card_uses_canonical_play_time_label() -> None:
    rom = FR_ROM.read_bytes()

    assert {
        _decode_pointer(rom, pointer_offset)
        for pointer_offset in TRAINER_CARD_TIME_POINTERS
    } == {"Durée jeu"}


def test_unrelated_save_summary_keeps_short_time_label() -> None:
    rom = FR_ROM.read_bytes()

    assert _decode_pointer(rom, SAVE_SUMMARY_TIME_POINTER) == "Temps"
