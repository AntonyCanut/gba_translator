"""Régression des classes de dresseurs aquatiques françaises (issue #161)."""

from __future__ import annotations

from pathlib import Path

import pytest

from languages.fr.patches.trainer_class_names import (
    CELL_STRIDE,
    CLASS_COUNT,
    TABLE_BASE,
    _load_combined,
    patch,
)
from src.core.text_codec import TextDecoder

COMBINED_FR = Path("languages/fr/combined_fr.txt")
FR_ROM = Path("output/roms/GenedRom-fr.gba")

SWIMMER_MALE_OFFSET = 0x23E8E6
SWIMMER_FEMALE_OFFSET = 0x23E91A
TUBER_OFFSET = 0x23EA6C

EXPECTED_CLASSES = {
    SWIMMER_MALE_OFFSET: "Nageur♂",
    SWIMMER_FEMALE_OFFSET: "Nageuse♀",
    TUBER_OFFSET: "Flotteur",
}


def _decode_cell(rom: bytes | bytearray, offset: int) -> str:
    """Décode une cellule complète de ``gTrainerClassNames``."""
    return TextDecoder.decode_pokemon(bytes(rom[offset : offset + CELL_STRIDE]))


def test_patch_writes_all_swimmer_class_labels_in_french() -> None:
    """Le patch doit traduire la classe Tuber par le terme exact « Flotteur »."""
    rom = bytearray(TABLE_BASE + CLASS_COUNT * CELL_STRIDE)
    combined = _load_combined(COMBINED_FR)

    patch(rom, combined)

    for offset, expected in EXPECTED_CLASSES.items():
        assert _decode_cell(rom, offset) == expected


@pytest.mark.rom
def test_built_rom_contains_all_swimmer_class_labels() -> None:
    """La ROM livrée doit contenir les trois libellés réellement consommés."""
    rom = FR_ROM.read_bytes()

    for offset, expected in EXPECTED_CLASSES.items():
        assert 0xFF in rom[offset : offset + CELL_STRIDE]
        assert _decode_cell(rom, offset) == expected
