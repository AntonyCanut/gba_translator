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
EXPECTED_PLAY_TIME_BYTES = bytes.fromhex("BE E9 E6 1B D9 00 DE D9 E9 FF")


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


def test_trainer_card_label_has_exact_bytes_and_terminator() -> None:
    rom = FR_ROM.read_bytes()
    targets = {
        int.from_bytes(rom[offset : offset + 4], "little") - ROM_BASE
        for offset in TRAINER_CARD_TIME_POINTERS
    }

    assert len(targets) == 1
    target = targets.pop()
    assert rom[target : target + len(EXPECTED_PLAY_TIME_BYTES)] == EXPECTED_PLAY_TIME_BYTES


def test_unrelated_save_summary_keeps_short_time_label() -> None:
    rom = FR_ROM.read_bytes()

    assert _decode_pointer(rom, SAVE_SUMMARY_TIME_POINTER) == "Temps"
