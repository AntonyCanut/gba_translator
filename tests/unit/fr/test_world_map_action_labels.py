"""Régressions des libellés d'action de la carte mondiale (#111)."""

import struct
from pathlib import Path

import pytest

from languages.fr.patches.world_map_action_labels import (
    ANNUL_BYTES,
    ANNUL_CPU_ADDR,
    ANNUL_STR_OFFSET,
    ANNULER_BYTES,
    CANCEL_LABEL_POINTERS,
    apply,
)
from src.core.text_codec import TextDecoder


ROOT = Path(__file__).resolve().parents[3]
BUILT_ROM = ROOT / "output/roms/GenedRom-fr.gba"
ROM_BASE = 0x08000000
MOVE_LABEL_POINTER = 0xA6CAAC
ROM_SIZE = 0x2000000
SHARED_ANNULER_OFFSET = 0xE00000


def _read_pointed_text(rom: bytes, pointer_offset: int) -> str:
    """Décode la chaîne terminée pointée depuis ``pointer_offset``."""
    encoded_pointer = rom[pointer_offset:pointer_offset + 4]
    text_offset = int.from_bytes(encoded_pointer, "little") - ROM_BASE
    terminator = rom.index(0xFF, text_offset)
    return TextDecoder.decode_pokemon(rom[text_offset:terminator + 1])


def _fake_rom() -> bytearray:
    """Construit une ROM minimale où la carte partage « Annuler »."""
    rom = bytearray(ROM_SIZE)
    rom[SHARED_ANNULER_OFFSET:SHARED_ANNULER_OFFSET + len(ANNULER_BYTES)] = (
        ANNULER_BYTES
    )
    for pointer in CANCEL_LABEL_POINTERS:
        struct.pack_into("<I", rom, pointer, ROM_BASE + SHARED_ANNULER_OFFSET)
    rom[ANNUL_STR_OFFSET:ANNUL_STR_OFFSET + len(ANNUL_BYTES)] = b"\xff" * len(
        ANNUL_BYTES
    )
    return rom


def test_cancel_patch_repoints_only_world_map_literals() -> None:
    """Le patch doit laisser intacte la chaîne « Annuler » partagée."""
    rom = _fake_rom()

    assert apply(rom) == 2
    assert rom[
        SHARED_ANNULER_OFFSET:SHARED_ANNULER_OFFSET + len(ANNULER_BYTES)
    ] == ANNULER_BYTES
    assert rom[ANNUL_STR_OFFSET:ANNUL_STR_OFFSET + len(ANNUL_BYTES)] == ANNUL_BYTES
    assert all(
        struct.unpack_from("<I", rom, pointer)[0] == ANNUL_CPU_ADDR
        for pointer in CANCEL_LABEL_POINTERS
    )


def test_cancel_patch_is_idempotent() -> None:
    """Une seconde application ne doit rien modifier."""
    rom = _fake_rom()

    assert apply(rom) == 2
    assert apply(rom) == 0


@pytest.mark.rom
def test_world_map_uses_short_move_and_cancel_labels() -> None:
    """La carte doit afficher « Dépl. » et « Annul. » sans débordement."""
    rom = BUILT_ROM.read_bytes()

    assert _read_pointed_text(rom, MOVE_LABEL_POINTER) == "Dépl."
    assert all(
        _read_pointed_text(rom, pointer) == "Annul."
        for pointer in CANCEL_LABEL_POINTERS
    )
