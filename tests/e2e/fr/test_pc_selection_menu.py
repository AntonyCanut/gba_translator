"""E2E: the "which PC" menu renders in French (GitHub issue #18).

The PC-access menu ("Which PC should be accessed?") listed three untranslated
strings:

  * 0x1A508A — the question itself, "Which PC should be accessed?", was left
    in place (not relocated) and is read verbatim at that fixed offset.
  * 0x417BB6 — the player's own entry, "<player buffer>'s PC", was entirely
    *missing* from combined_fr.txt (never translated at all — the untranslated
    English "PLAYER's PC" is what the reporter saw in game).
  * 0x417BD3 — "Prof. Log's PC" was translated but missing the grammatically
    required "du".

0x417BB6 and 0x417BD3 sit in the same compact, pointer-reachable string table
as the other menu entries ("Ayla's PC", "Hall of Fame", "Log Off"...) and get
*relocated* by the generic builder when the French text no longer fits the
original English cell — so the live text must be read by following the GBA
pointer, not by reading the fixed original offset (which is left holding stale
bytes after relocation).
"""

import struct
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder

SOURCE_ROM = Path("input/roms/patchedfrenchrom.gba")
FR_ROM = Path("output/roms/GenedRom-fr.gba")
GBA_BASE = 0x08000000


def _decode_at(rom: bytes, offset: int, limit: int = 60) -> str:
    chunk = rom[offset:offset + limit]
    end = chunk.find(b"\xff")
    raw = chunk if end == -1 else chunk[:end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True)


def _resolve_live_pointer(source_rom: bytes, built_rom: bytes, original_offset: int) -> int:
    """Return the file offset the game actually reads for `original_offset`.

    The pointer *table slot* is a fixed ROM location, found by searching the
    (unbuilt) source ROM for a pointer that still targets the original
    address. The *value* stored there may have been rewritten by the builder
    to point at a relocated copy, so it must be read back from the built ROM.
    """
    needle = struct.pack("<I", original_offset + GBA_BASE)
    slot = source_rom.find(needle)
    assert slot != -1, f"No pointer to 0x{original_offset:X} found in the source ROM"
    (target,) = struct.unpack_from("<I", built_rom, slot)
    return target - GBA_BASE


@pytest.fixture(scope="module")
def source_rom_data():
    if not SOURCE_ROM.exists():
        pytest.skip(f"ROM not found: {SOURCE_ROM}")
    return SOURCE_ROM.read_bytes()


@pytest.fixture(scope="module")
def rom_data():
    if not FR_ROM.exists():
        pytest.skip(f"ROM not found: {FR_ROM}")
    return FR_ROM.read_bytes()


@pytest.mark.rom
class TestPcSelectionMenuFrench:
    def test_which_pc_question_is_french(self, rom_data):
        text = _decode_at(rom_data, 0x1A508A)
        assert text == "Accéder à quel PC ?", f"0x1A508A: got {text!r}"

    def test_player_pc_entry_is_translated(self, source_rom_data, rom_data):
        target = _resolve_live_pointer(source_rom_data, rom_data, 0x417BB6)
        text = _decode_at(rom_data, target)
        assert text == "PC de <0xFD>À", (
            f"0x417BB6 (live @ 0x{target:X}): got {text!r} — "
            "player's own PC entry must read \"PC de <player>\", not the "
            "untranslated English \"PLAYER's PC\""
        )

    def test_prof_log_pc_entry_has_du(self, source_rom_data, rom_data):
        target = _resolve_live_pointer(source_rom_data, rom_data, 0x417BD3)
        text = _decode_at(rom_data, target)
        assert text == "PC du Prof. Log", f"0x417BD3 (live @ 0x{target:X}): got {text!r}"
