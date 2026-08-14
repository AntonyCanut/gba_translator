"""ROM-level proof for canonical English Pokémon names in the German build."""

from __future__ import annotations

from pathlib import Path

import pytest

from languages.de.tools.audit_species_names import audit_rom
from languages.fr.patches.species_names import (
    SPECIES_COUNT,
    SPECIES_STRIDE,
    SPECIES_TABLE_OFFSET,
    _decode_cell,
)

ROOT = Path(__file__).resolve().parents[3]
ENGLISH = ROOT / "input/roms/englishrom.gba"
GERMAN = ROOT / "output/roms/GenedRom-de.gba"
COMBINED = ROOT / "languages/de/combined_de.txt"
pytestmark = pytest.mark.rom


def test_all_1293_species_cells_are_byte_identical_to_english_source():
    english = ENGLISH.read_bytes()
    german = GERMAN.read_bytes()
    end = SPECIES_TABLE_OFFSET + SPECIES_COUNT * SPECIES_STRIDE

    assert german[SPECIES_TABLE_OFFSET:end] == english[SPECIES_TABLE_OFFSET:end]
    assert [_decode_cell(german, SPECIES_TABLE_OFFSET + i * SPECIES_STRIDE) for i in (0, 411, 951, 1292)] == [
        "Bulbasaur",
        "Bad Egg",
        "Gumshoos",
        "Urshifu",
    ]


def test_no_french_species_name_is_reachable_through_a_live_pointer():
    table_matches, leaks = audit_rom(GERMAN, ENGLISH, COMBINED)

    assert table_matches
    assert leaks == []
