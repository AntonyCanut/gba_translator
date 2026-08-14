"""Gardes ROM des noms de capacités français à cellule fixe."""

from pathlib import Path

import pytest

from languages.fr.patches.move_names import (
    LEGACY_TABLE_OFFSET,
    MOVE_STRIDE,
    _decode_cell,
    resolve_live_base,
)

ROOT = Path(__file__).resolve().parents[3]
FR_ROM = ROOT / "output" / "roms" / "GenedRom-fr.gba"

pytestmark = pytest.mark.rom


def test_issue_183_touching_stare_uses_readable_abbreviation() -> None:
    """Le build FR doit livrer « RegarTouchan », pas « RegarTouchnt »."""
    rom = FR_ROM.read_bytes()
    source_offset = 0xA42186
    index, remainder = divmod(source_offset - LEGACY_TABLE_OFFSET, MOVE_STRIDE)
    assert remainder == 0

    live_offset = resolve_live_base(rom) + index * MOVE_STRIDE

    assert _decode_cell(rom, live_offset) == "RegarTouchan"
