"""Tests for the German move/species fixed-table patches (issue #81)."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from languages.de.patches import move_names as de_move_names  # noqa: E402
from languages.de.patches import species_names as de_species_names  # noqa: E402
from languages.fr.patches import move_names as base_move_names  # noqa: E402
from languages.fr.patches import species_names as base_species_names  # noqa: E402


def test_move_names_loads_fallback_for_missing_early_moves():
    translations = de_move_names.load_translations()

    pound = base_move_names.LEGACY_TABLE_OFFSET + 1 * base_move_names.MOVE_STRIDE
    karate_chop = base_move_names.LEGACY_TABLE_OFFSET + 2 * base_move_names.MOVE_STRIDE
    brick_break = base_move_names.LEGACY_TABLE_OFFSET + 280 * base_move_names.MOVE_STRIDE

    assert translations[pound] == "Klaps"
    assert translations[karate_chop] == "Karateschl"
    assert translations[brick_break] == "Ziegelbruch"
    assert de_move_names._fits_cell(translations[brick_break])


def test_species_names_uses_fallback_when_combined_entry_is_too_long():
    translations = de_species_names.load_translations()

    bad_egg = (
        base_species_names.SPECIES_TABLE_OFFSET
        + 411 * base_species_names.SPECIES_STRIDE
    )
    yungoos = (
        base_species_names.SPECIES_TABLE_OFFSET
        + 951 * base_species_names.SPECIES_STRIDE
    )

    assert translations[bad_egg] == "Schl. Ei"
    assert translations[yungoos] == "Manguspekt"
    assert de_species_names._fits_cell(translations[bad_egg])
    assert de_species_names._fits_cell(translations[yungoos])


def test_fallback_tables_are_cell_width_safe():
    for name in de_move_names._load_fallback().values():
        assert de_move_names._fits_cell(name), name
    for name in de_species_names._load_fallback().values():
        assert de_species_names._fits_cell(name), name


def test_de_descriptor_wires_both_steps():
    descriptor = yaml.safe_load(
        (ROOT / "languages" / "de" / "lang.yaml").read_text(encoding="utf-8")
    )
    patches = descriptor["patches"]
    assert "move_names" in patches, "move_names not wired into languages/de/lang.yaml"
    assert "species_names" in patches, "species_names not wired into languages/de/lang.yaml"
