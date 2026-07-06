"""Regression guard for the clean-base move-name table (R-17 / T-38).

After R-17, ``input/roms/englishrom.gba`` is a genuinely clean vanilla Unbound
ROM and the move-name table lives at its stock offset **0xA40A10** (English
names). The old French-patched base — now ``input/roms/patchedfrenchrom.gba``
— had the table relocated to free space at **0x1B2980**. An earlier revision
of ``languages/fr/patches/move_names.py`` hard-coded 0x1B2980 as "the live
table", so on the clean base it wrote Italian names to unreferenced free space
and left English at the real table: IT shipped English move names.

These tests pin the two facts that keep the fix honest:
  1. ``resolve_live_base`` follows the ROM's own pointer, so it returns
     0xA40A10 on the clean base and 0x1B2980 on the French-patched base.
  2. Patching the clean base with ``combined_it.txt`` lands Italian names at
     the live table (0xA40A10) and never touches the dead relocation offset.

They read the input ROMs directly, so no build is required.
"""

from pathlib import Path

import pytest

from languages.fr.patches.move_names import (
    LEGACY_TABLE_OFFSET,
    MOVE_STRIDE,
    RELOCATED_TABLE_OFFSET,
    _decode_cell,
    _parse_combined,
    apply_to_rom,
    resolve_live_base,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CLEAN_ROM = REPO_ROOT / "input/roms/englishrom.gba"
PATCHED_ROM = REPO_ROOT / "input/roms/patchedfrenchrom.gba"
IT_COMBINED = REPO_ROOT / "languages/it/combined_it.txt"


def _cell(data, base, index):
    return _decode_cell(data, base + index * MOVE_STRIDE)


@pytest.mark.rom
class TestMoveNamesCleanBase:
    def test_resolves_clean_base_to_stock_offset(self):
        if not CLEAN_ROM.exists():
            pytest.skip("clean englishrom.gba not present")
        data = CLEAN_ROM.read_bytes()
        assert resolve_live_base(data) == LEGACY_TABLE_OFFSET  # 0xA40A10
        # Sanity: the stock table really holds English move names here.
        assert _cell(data, LEGACY_TABLE_OFFSET, 1) == "Pound"
        assert _cell(data, LEGACY_TABLE_OFFSET, 2) == "Karate Chop"

    def test_resolves_patched_base_to_relocated_offset(self):
        if not PATCHED_ROM.exists():
            pytest.skip("patchedfrenchrom.gba not present")
        data = PATCHED_ROM.read_bytes()
        assert resolve_live_base(data) == RELOCATED_TABLE_OFFSET  # 0x1B2980

    def test_italian_names_land_at_live_table_on_clean_base(self):
        if not CLEAN_ROM.exists() or not IT_COMBINED.exists():
            pytest.skip("clean ROM or combined_it.txt not present")
        data = bytearray(CLEAN_ROM.read_bytes())
        translations = _parse_combined(IT_COMBINED)

        patched, warnings = apply_to_rom(data, translations)

        assert patched > 800  # nearly the whole 894-entry roster is authored
        # Live table now Italian; the dead relocation offset stays blank.
        assert _cell(data, LEGACY_TABLE_OFFSET, 1) == "Botta"          # Pound
        assert _cell(data, LEGACY_TABLE_OFFSET, 2) == "Colpo Karate"   # Karate Chop
        assert _cell(data, RELOCATED_TABLE_OFFSET, 1) == ""            # untouched
