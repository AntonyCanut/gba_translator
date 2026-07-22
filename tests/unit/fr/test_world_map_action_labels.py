"""Régressions des libellés d'action de la carte mondiale (#111, #131)."""

from __future__ import annotations

import re
import struct
from pathlib import Path

import pytest

from src.text.charmap_data import CHAR_TO_BYTE


ROOT = Path(__file__).resolve().parents[3]
BUILT_ROM = ROOT / "output/roms/GenedRom-fr.gba"
COMBINED_FR = ROOT / "languages/fr/combined_fr.txt"
ROM_BASE = 0x08000000

# Chaînes « <bouton A> Cancel » propres aux variantes de la carte mondiale.
WORLD_MAP_CANCEL_OFFSETS = (0x418E95, 0x418E9E)
WORLD_MAP_CANCEL_POINTERS = (0xC06FC, 0xC1B28, 0xC50C0)
WORLD_MAP_CANCEL_TEXT = "{SE_SHOP}Annul."
WORLD_MAP_CANCEL_BYTES = bytes.fromhex("f800bbe2e2e9e0adff")

# Bandeaux de déplacement affichés en haut de la carte mondiale.
WORLD_MAP_HINT_OFFSET = 0x418E77
WORLD_MAP_MOVE_OFFSET = 0x418EB5
WORLD_MAP_HINT_POINTER = 0x9FB64
WORLD_MAP_MOVE_POINTERS = (0xC05D8, 0xC12E0, 0xC283C, 0xC4FE8)
WORLD_MAP_HINT_TEXT = "{DPAD_ANY}Dépl. {SE_SHOP}OK {B_BUTTON}Annul"
WORLD_MAP_MOVE_TEXT = "{DPAD_ANY}Dépl."
WORLD_MAP_HINT_CANCEL_SLOT_SIZE = 5
WORLD_MAP_HINT_BYTES = bytes.fromhex(
    "f80cbe1be4e0ad00f800c9c500f801bbe2e2e9e0ff"
)
WORLD_MAP_MOVE_BYTES = bytes.fromhex("f80cbe1be4e0adff")

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


def test_world_map_sources_use_complete_short_labels() -> None:
    """Les sources doivent contenir les formes courtes, point compris."""
    mapping = _load_last_wins(COMBINED_FR)

    assert mapping[WORLD_MAP_HINT_OFFSET] == WORLD_MAP_HINT_TEXT
    assert mapping[WORLD_MAP_MOVE_OFFSET] == WORLD_MAP_MOVE_TEXT
    assert {
        offset: mapping.get(offset)
        for offset in WORLD_MAP_CANCEL_OFFSETS
    } == {
        offset: WORLD_MAP_CANCEL_TEXT
        for offset in WORLD_MAP_CANCEL_OFFSETS
    }


def test_world_map_hint_cancel_fits_its_five_glyph_slot() -> None:
    """Le libellé B du bandeau ne doit pas déborder dans la carte."""
    mapping = _load_last_wins(COMBINED_FR)
    cancel_label = mapping[WORLD_MAP_HINT_OFFSET].rsplit("{B_BUTTON}", 1)[1]
    encoded_label = bytes(CHAR_TO_BYTE[character] for character in cancel_label)

    assert len(encoded_label) <= WORLD_MAP_HINT_CANCEL_SLOT_SIZE


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


@pytest.mark.rom
def test_world_map_move_hints_have_no_trailing_residue() -> None:
    """Le bandeau ne doit garder ni le « r » ni le point final hors cellule."""
    rom = BUILT_ROM.read_bytes()

    assert (
        _read_pointed_bytes(rom, WORLD_MAP_HINT_POINTER)
        == WORLD_MAP_HINT_BYTES
    )
    assert all(
        _read_pointed_bytes(rom, pointer) == WORLD_MAP_MOVE_BYTES
        for pointer in WORLD_MAP_MOVE_POINTERS
    )
