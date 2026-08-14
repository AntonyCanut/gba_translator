"""Décodage des tables terminologiques dans la ROM allemande construite."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from languages.de.patches import cfru_type_names, item_names, move_names, nature_names
from languages.fr.patches import ability_names as ability_table
from languages.fr.patches import move_names as move_table

pytestmark = pytest.mark.rom

ROOT = Path(os.environ.get("GBA_PROJECT_ROOT", Path(__file__).resolve().parents[3]))
DE_ROM = ROOT / "output/roms/GenedRom-de.gba"
EN_ROM = ROOT / "input/roms/englishrom.gba"


@pytest.fixture(scope="module")
def roms() -> tuple[bytes, bytes]:
    if not DE_ROM.exists() or not EN_ROM.exists():
        pytest.skip("ROM DE non construite — lancer make build-de")
    return EN_ROM.read_bytes(), DE_ROM.read_bytes()


def test_all_move_cells_decode_to_the_cfru_aligned_glossary(roms) -> None:
    english, german = roms
    base = move_table.resolve_live_base(german)
    entries = move_names.load_official_entries()

    for table_offset, expected in move_names.load_translations().items():
        index = (
            table_offset - move_table.LEGACY_TABLE_OFFSET
        ) // move_table.MOVE_STRIDE
        english_offset = move_table.LEGACY_TABLE_OFFSET + index * move_table.MOVE_STRIDE
        assert move_table._decode_cell(english, english_offset) == entries[index]["english"]
        offset = base + index * move_table.MOVE_STRIDE
        assert move_table._decode_cell(german, offset) == expected, index


def test_corrected_ability_cells_decode_to_official_names(roms) -> None:
    english, german = roms
    expected_by_english = {
        "Own Tempo": "Tempomacher",
        "Poison Heal": "Aufheber",
        "Tangled Feet": "Fußangel",
        "Battle Bond": "Freundschaftsakt",
        "Prism Armor": "Prismarüstung",
        "Electric Surge": "Elektro-Erzeuger",
        "Symbiosis": "Nutznießer",
        "Vital Spirit": "Munterkeit",
    }
    found = set()
    for offset in range(
        ability_table.ABILITY_TABLE_OFFSET,
        ability_table.ABILITY_TABLE_LAST + 1,
        ability_table.ABILITY_STRIDE,
    ):
        source = ability_table._decode_cell(english, offset)
        if source in expected_by_english:
            assert ability_table._decode_cell(german, offset) == expected_by_english[source]
            found.add(source)
    assert found == set(expected_by_english)


def test_corrected_item_cells_decode_to_official_or_constrained_names(roms) -> None:
    english, german = roms
    expected = {
        "Focus Band": "Fokusband",
        "Sharp Beak": "Spitz.Schnab.",
        "Shell Bell": "Muschelglocke",
        "Member Card": "Mitgl.Karte",
        "Letter": "Brief an Troy",
    }
    found = set()
    for index in range(item_names.SCAN_COUNT):
        offset = item_names.ITEM_TABLE_BASE + index * item_names.ITEM_STRIDE
        source = item_names.decode_name(english, offset)
        if source in expected:
            assert item_names.decode_name(german, offset) == expected[source]
            found.add(source)
    assert found == set(expected)


def test_natures_and_constrained_type_table_decode_cleanly(roms) -> None:
    _english, german = roms
    assert nature_names.verify(german) == []
    for offset, _english_name, expected in cfru_type_names.TYPE_PATCHES:
        assert cfru_type_names._read_until(bytearray(german), offset, 0x00) == expected
    for offset, _english_name, expected in cfru_type_names.CONDITION_PATCHES:
        assert cfru_type_names._read_until(bytearray(german), offset, 0xFF) == expected
