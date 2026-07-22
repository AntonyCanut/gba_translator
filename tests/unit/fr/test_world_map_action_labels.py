"""Régressions des libellés d'action de la carte mondiale (#111, #131)."""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
BUILT_ROM = ROOT / "output/roms/GenedRom-fr.gba"
COMBINED_FR = ROOT / "languages/fr/combined_fr.txt"
ROM_BASE = 0x08000000

# Chaînes « <bouton A> Cancel » propres aux variantes de la carte mondiale.
WORLD_MAP_CANCEL_OFFSETS = (0x418E95, 0x418E9E)
WORLD_MAP_CANCEL_POINTERS = (0xC06FC, 0xC1B28, 0xC50C0)
WORLD_MAP_CANCEL_TEXT = "{SE_SHOP}Annul."
WORLD_MAP_CANCEL_BYTES = bytes.fromhex("f800bbe2e2e9e0adff")

# Ces deux références appartiennent au menu Équipe, pas à la carte mondiale.
PARTY_CANCEL_POINTERS = (0xA6CA2C, 0xA6CA64)
ANNULER_BYTES = bytes.fromhex("bbe2e2e9e0d9e6ff")

_LINE_RE = re.compile(r"^\s*0x([0-9a-fA-F]+)\s*:\s*(.*)$")


def _load_last_wins(path: Path) -> dict[int, str]:
    """Charge les traductions avec la même règle « dernière occurrence gagne »."""
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _LINE_RE.match(line)
        if match:
            mapping[int(match.group(1), 16)] = match.group(2)
    return mapping


def _read_pointed_bytes(rom: bytes, pointer_offset: int) -> bytes:
    """Retourne la chaîne terminée pointée depuis ``pointer_offset``."""
    text_pointer = struct.unpack_from("<I", rom, pointer_offset)[0]
    assert ROM_BASE <= text_pointer < ROM_BASE + len(rom)
    text_offset = text_pointer - ROM_BASE
    terminator = rom.index(0xFF, text_offset)
    return rom[text_offset:terminator + 1]


def test_world_map_cancel_sources_are_abbreviated() -> None:
    """Les deux chaînes source de la carte doivent demander « Annul. »."""
    mapping = _load_last_wins(COMBINED_FR)

    assert {
        offset: mapping.get(offset)
        for offset in WORLD_MAP_CANCEL_OFFSETS
    } == {
        offset: WORLD_MAP_CANCEL_TEXT
        for offset in WORLD_MAP_CANCEL_OFFSETS
    }


@pytest.mark.rom
def test_world_map_cancel_pointers_render_short_label() -> None:
    """Toutes les variantes de la carte doivent afficher « Annul. »."""
    rom = BUILT_ROM.read_bytes()

    assert all(
        _read_pointed_bytes(rom, pointer) == WORLD_MAP_CANCEL_BYTES
        for pointer in WORLD_MAP_CANCEL_POINTERS
    )


@pytest.mark.rom
def test_party_cancel_entries_keep_full_shared_label() -> None:
    """Les entrées du menu Équipe ne doivent pas être prises pour la carte."""
    rom = BUILT_ROM.read_bytes()

    assert all(
        _read_pointed_bytes(rom, pointer) == ANNULER_BYTES
        for pointer in PARTY_CANCEL_POINTERS
    )
