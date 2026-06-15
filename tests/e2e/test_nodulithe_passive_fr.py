"""E2E: Nodulithe's passive ability renders without a typo in the FR ROM.

Bug report (parent ticket P-15 — "Texte combat Pokémon sauvage"):
    « grosse faute de frappe sur le passif de Nodulithe »

Nodulithe (Roggenrola) triggers the ability **Weak Armor** in battle, whose
official French name is **Armurouillée** (a portmanteau of "Armure" +
"rouillée"). The activation message lowers Defense and sharply raises Speed.

The garbled rendering seen in the report — the ability-name cell plus the
"X de Vitesse fortementaugmente !" message — came from three regressions that
have since been fixed:
  * the ability-name cell at 0xA37069 (fixed-width 17-byte slot, no pointer);
  * the stat-change verb adverb losing its trailing space
    ("fortement " → "fortementaugmente");
  * the stat-change template word order ("{stat} de {name}\n{verb}").

These tests lock those fixes so a future rebuild (which re-points / restores
EN strings — see scripts/repoint_stale_text_pointers.py) cannot reintroduce
the typo.
"""

import json
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

FR_ROM = Path("output/roms/GenedRom-fr.gba")
FR_TRANSLATION = Path("output/translation/2026-06-12_translation_ready.json")

# Ability-name table: fixed-width cells of 17 bytes (name + 0xFF + padding).
# "Weak Armor" lives at file offset 0xA37069; the engine reads the cell in
# place, so the FR name is written here verbatim (never relocated).
_ABILITY_CELL_OFFSET = 0xA37069
_ABILITY_CELL_STRIDE = 0x11
_EXPECTED_ABILITY_FR = "Armurouillée"


def _decode_cell(rom_data: bytes, offset: int, stride: int) -> str:
    cell = rom_data[offset:offset + stride]
    end = cell.find(b"\xFF")
    raw = cell if end == -1 else cell[:end]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


@pytest.fixture(scope="module")
def rom_data():
    if not FR_ROM.exists():
        pytest.skip(f"ROM not found: {FR_ROM}")
    return FR_ROM.read_bytes()


@pytest.fixture(scope="module")
def translations():
    if not FR_TRANSLATION.exists():
        pytest.skip(f"Translation file not found: {FR_TRANSLATION}")
    data = json.loads(FR_TRANSLATION.read_text(encoding="utf-8"))
    return {t["offset"]: t for t in data["translations"]}


@pytest.mark.rom
class TestNodulithePassiveName:
    def test_weak_armor_name_is_armurouillee(self, rom_data):
        """0xA37069 must decode to the official FR name, no typo."""
        name = _decode_cell(rom_data, _ABILITY_CELL_OFFSET, _ABILITY_CELL_STRIDE)
        assert name == _EXPECTED_ABILITY_FR, (
            f"Weak Armor FR name at 0x{_ABILITY_CELL_OFFSET:X}: "
            f"got {name!r}, expected {_EXPECTED_ABILITY_FR!r}"
        )

    def test_weak_armor_name_well_formed(self, rom_data):
        """No fused word / dropped space inside the ability name cell."""
        name = _decode_cell(rom_data, _ABILITY_CELL_OFFSET, _ABILITY_CELL_STRIDE)
        assert name.strip() == name, "Ability name has stray leading/trailing space"
        assert "  " not in name, "Ability name contains a double space"
        assert name.isascii() is False, "Ability name should keep its 'é' accent"


@pytest.mark.rom
class TestWeakArmorActivationMessage:
    """The 'passive triggered' message that read 'fortementaugmente !'."""

    def test_adverb_keeps_trailing_space(self, translations):
        """'sharply'/'harshly' → 'fortement ' (trailing space restored)."""
        for offset in (0x3FCB41, 0x3FCB50):
            entry = translations.get(offset)
            assert entry is not None, f"Missing stat adverb entry at 0x{offset:X}"
            assert entry["translation"] == "fortement ", (
                f"0x{offset:X}: got {entry['translation']!r}, "
                "expected 'fortement ' (trailing space)"
            )

    def test_stat_template_word_order(self, translations):
        """Template must read '{stat} de {name}\\n{verb}', not 'name de stat'."""
        # Control codes are stored as literal "<0xFD>" placeholders in the
        # translation JSON. FD00 = stat buffer, FD0F = battler-name buffer.
        entry = translations.get(0x3FCB5F)
        assert entry is not None, "Missing stat-change template at 0x3FCB5F"
        assert entry["translation"] == "<0xFD><0x00> de <0xFD><0x0F>\n<0xFD><0x01>", (
            f"Unexpected stat template: {entry['translation']!r}"
        )
