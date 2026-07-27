"""Regression guard for the live level-up stat table (GitHub issue #149)."""

from pathlib import Path

import pytest


FR_ROM = Path("output/roms/GenedRom-fr.gba")
GBA_BASE = 0x08000000
LEVELUP_STAT_POINTER = 0x459B48
LEVELUP_STAT_TABLE_LITERALS = (0x11E930, 0x11EA40)
EXPECTED_LABEL = bytes.fromhex("ca d0 00 fc 06 00 c7 d5 ec ad")
OLD_LABEL = bytes.fromhex("fc 06 00 c7 bb d2 ad fc 06 02 00 ca d0")


def _read_terminated(rom: bytes, offset: int) -> bytes:
    terminator = rom.index(0xFF, offset)
    return rom[offset:terminator]


@pytest.mark.rom
@pytest.mark.skipif(not FR_ROM.exists(), reason="FR ROM not built")
def test_levelup_live_max_hp_pointer_renders_pv_max():
    rom = FR_ROM.read_bytes()
    target = int.from_bytes(
        rom[LEVELUP_STAT_POINTER:LEVELUP_STAT_POINTER + 4],
        "little",
    ) - GBA_BASE
    label = _read_terminated(rom, target)

    assert target == 0x41B2A9
    assert label == EXPECTED_LABEL, (
        f"level-up pointer 0x{LEVELUP_STAT_POINTER:X} -> 0x{target:X} "
        f"still renders {label.hex(' ')} instead of PV Max."
    )
    assert label != OLD_LABEL


@pytest.mark.rom
@pytest.mark.skipif(not FR_ROM.exists(), reason="FR ROM not built")
def test_levelup_code_reads_the_guarded_stat_table():
    rom = FR_ROM.read_bytes()
    expected_pointer = GBA_BASE + LEVELUP_STAT_POINTER

    for literal_offset in LEVELUP_STAT_TABLE_LITERALS:
        literal = int.from_bytes(
            rom[literal_offset:literal_offset + 4],
            "little",
        )
        assert literal == expected_pointer, (
            f"level-up code literal 0x{literal_offset:X} reads "
            f"0x{literal:X} instead of stat table 0x{expected_pointer:X}"
        )
