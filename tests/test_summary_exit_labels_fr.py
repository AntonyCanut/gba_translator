"""Régressions des libellés de sortie des écrans Pokémon (#181)."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from scripts.apply_combined_fr import _load_combined


ROOT = Path(__file__).resolve().parent.parent
COMBINED_FR = ROOT / "languages" / "fr" / "combined_fr.txt"
BUILT_FR_ROM = ROOT / "output" / "roms" / "GenedRom-fr.gba"
ROM_BASE = 0x08000000

EXPECTED_TEXTS = {
    0x419C62: "{DPAD_RIGHT}Page {SE_SHOP}Sortir",
    0x419C72: "{SE_SHOP}Sortir",
}
EXPECTED_POINTER_BYTES = {
    0x137D80: bytes.fromhex("f809cad5dbd900f800cde3e6e8dde6ff"),
    0x137D88: bytes.fromhex("f800cde3e6e8dde6ff"),
}


def _read_pointed_bytes(rom: bytes, pointer_offset: int) -> bytes:
    """Lit une chaîne CFRU terminée depuis une cellule de pointeur."""
    text_pointer = struct.unpack_from("<I", rom, pointer_offset)[0]
    assert ROM_BASE <= text_pointer < ROM_BASE + len(rom)
    text_offset = text_pointer - ROM_BASE
    return rom[text_offset:rom.index(0xFF, text_offset) + 1]


def test_summary_exit_labels_use_sortir_in_translation_source() -> None:
    """Les deux variantes dédiées doivent exprimer une sortie, pas une annulation."""
    translations, _ = _load_combined(COMBINED_FR)

    assert {
        offset: translations[offset]
        for offset in EXPECTED_TEXTS
    } == EXPECTED_TEXTS


@pytest.mark.rom
def test_summary_exit_labels_render_sortir_in_built_rom() -> None:
    """Les cellules réellement lues par les deux écrans doivent rendre « Sortir »."""
    rom = BUILT_FR_ROM.read_bytes()

    assert {
        pointer: _read_pointed_bytes(rom, pointer)
        for pointer in EXPECTED_POINTER_BYTES
    } == EXPECTED_POINTER_BYTES
