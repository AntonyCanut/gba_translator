"""Tests for the German move table and canonical EN species table."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from languages.de.patches import move_names as de_move_names  # noqa: E402
from languages.de.patches import species_names as de_species_names  # noqa: E402
from languages.fr.patches import move_names as base_move_names  # noqa: E402
from languages.fr.patches import species_names as base_species_names  # noqa: E402


def test_move_names_loads_cfru_aligned_official_names():
    translations = de_move_names.load_translations()

    pound = base_move_names.LEGACY_TABLE_OFFSET + 1 * base_move_names.MOVE_STRIDE
    karate_chop = base_move_names.LEGACY_TABLE_OFFSET + 2 * base_move_names.MOVE_STRIDE
    brick_break = base_move_names.LEGACY_TABLE_OFFSET + 280 * base_move_names.MOVE_STRIDE

    assert translations[pound] == "Klaps"
    assert translations[karate_chop] == "Karateschlag"
    assert translations[brick_break] == "Durchbruch"
    assert de_move_names._fits_cell(translations[brick_break])


def test_species_names_restores_all_1293_cells_byte_for_byte():
    start = base_species_names.SPECIES_TABLE_OFFSET
    size = base_species_names.SPECIES_COUNT * base_species_names.SPECIES_STRIDE
    end = start + size
    english = bytearray(b"\xA5" * (end + 1))
    target = bytearray(b"\x5A" * (end + 1))

    changed = de_species_names.restore_species_table(target, english)

    assert changed == base_species_names.SPECIES_COUNT
    assert target[start:end] == english[start:end]
    assert target[start - 1] == 0x5A
    assert target[end] == 0x5A


def test_species_names_restore_is_idempotent():
    start = base_species_names.SPECIES_TABLE_OFFSET
    end = start + base_species_names.SPECIES_COUNT * base_species_names.SPECIES_STRIDE
    english = bytearray(b"\xA5" * end)
    target = bytearray(english)

    assert de_species_names.restore_species_table(target, english) == 0


def test_species_names_restore_rejects_truncated_rom_without_mutating_target():
    start = base_species_names.SPECIES_TABLE_OFFSET
    end = start + base_species_names.SPECIES_COUNT * base_species_names.SPECIES_STRIDE
    english = bytearray(b"\xA5" * (end - 1))
    target = bytearray(b"\x5A" * end)
    before = bytes(target)

    with pytest.raises(ValueError, match="species table"):
        de_species_names.restore_species_table(target, english)

    assert target == before


def test_glossary_display_names_are_cell_width_safe():
    for name in de_move_names.load_translations().values():
        assert de_move_names._fits_cell(name), name


def test_de_descriptor_wires_both_steps():
    descriptor = yaml.safe_load(
        (ROOT / "languages" / "de" / "lang.yaml").read_text(encoding="utf-8")
    )
    patches = descriptor["patches"]
    assert "move_names" in patches, "move_names not wired into languages/de/lang.yaml"
    assert "species_names" in patches, "species_names not wired into languages/de/lang.yaml"
    assert patches.index("species_names") > patches.index("worldmap_junction_panels")
    assert patches.index("species_names") < patches.index("collision_check")
