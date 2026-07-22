"""Behavioural guard for the deterministic floor-indicator patch (#27 / #100).

`languages/fr/patches/floor_indicators.py` is the class-3 fix that makes the
floor pop-up ("1F"→"RDC", "2F"→"1E"…, "B1F"→"-1"…) persistent: it writes the 15
French labels to a fixed reserved padding region and repoints every one of the
six duplicate pointer tables to that copy. This test proves the patch:

  * repoints *every* floor pointer to the correct French label (no English
    residue, the exact bug #100 reported as "still not translated");
  * repairs a merged/mis-terminated "RDC1E" style corruption instead of
    aborting on it;
  * is deterministic (same bytes, same offset, every run) and idempotent.

It runs fully offline on a synthetic ROM so it stays in the fast suite; a
guarded check against the real built ROM confirms the wiring end to end.
"""

from __future__ import annotations

import importlib.util
import struct
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

_spec = importlib.util.spec_from_file_location(
    "floor_indicators_patch", REPO_ROOT / "languages/fr/patches/floor_indicators.py"
)
fi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fi)

from src.core.text_codec import TextDecoder  # noqa: E402

ROM_BASE = 0x08000000
ROM_SIZE = 0x2000000
POINTER_TABLE_OFFSETS = (0x100000, 0x100100, 0x100200)  # 3 duplicate tables


def _decode_at(rom: bytes, cpu_addr: int) -> str:
    off = cpu_addr - ROM_BASE
    end = rom.find(b"\xFF", off)
    return TextDecoder.decode_pokemon(bytes(rom[off:end + 1]), preserve_unknown=True)


def _build_synthetic_rom() -> bytearray:
    """A minimal ROM with three pointer tables aimed at the floor cells."""
    rom = bytearray(b"\x00" * ROM_SIZE)
    rom[0xB2] = 0x96  # GBA logo checksum byte the patch validates against
    # Reserved tail padding must read as free (all 0xFF).
    rom[fi.FLOOR_STR_OFFSET:fi.FLOOR_STR_OFFSET + 0x100] = b"\xFF" * 0x100
    # Three duplicate pointer tables, each pointing at the 15 EN floor cells.
    for table in POINTER_TABLE_OFFSETS:
        for i, en_off in enumerate(fi.FR_LABELS):
            struct.pack_into("<I", rom, table + i * 4, ROM_BASE + en_off)
    return rom


def _all_slots_correct(rom: bytes, source: bytes) -> bool:
    for en_off, slots in fi._find_slots(source).items():
        for slot in slots:
            ptr = struct.unpack_from("<I", rom, slot)[0]
            if _decode_at(rom, ptr) != fi.FR_LABELS[en_off]:
                return False
    return True


def test_encodings_roundtrip_to_expected_labels():
    for label in fi.FR_LABELS.values():
        encoded = fi._encode(label)
        assert encoded.endswith(b"\xFF")
        assert TextDecoder.decode_pokemon(encoded, preserve_unknown=True) == label


def test_apply_repoints_every_slot_to_french():
    rom = _build_synthetic_rom()
    source = bytes(rom)
    patched = fi.apply(rom, source)

    # 3 tables x 15 cells = 45 pointer slots, all repointed on a fresh ROM.
    assert patched == 45
    assert _all_slots_correct(rom, source)
    # No slot may still resolve to an English residue ("1F", "B1F"…).
    for en_off, slots in fi._find_slots(source).items():
        for slot in slots:
            assert not _decode_at(rom, struct.unpack_from("<I", rom, slot)[0]).endswith("F")


def test_apply_is_idempotent():
    rom = _build_synthetic_rom()
    source = bytes(rom)
    assert fi.apply(rom, source) == 45
    assert fi.apply(rom, source) == 0  # nothing left to change


def test_apply_is_deterministic():
    rom_a = _build_synthetic_rom()
    rom_b = _build_synthetic_rom()
    src = bytes(rom_a)
    fi.apply(rom_a, src)
    fi.apply(rom_b, src)
    end = fi.FLOOR_STR_OFFSET + 0x100
    assert rom_a[fi.FLOOR_STR_OFFSET:end] == rom_b[fi.FLOOR_STR_OFFSET:end]
    assert bytes(rom_a) == bytes(rom_b)


def test_repairs_merged_rdc1e_corruption():
    """The 'RDC1E' merge (dropped terminator) that shipped must be repaired."""
    rom = _build_synthetic_rom()
    source = bytes(rom)
    # Simulate the corruption: an in-place table where RDC lost its terminator.
    rom[0x41803A:0x41803A + 6] = bytes.fromhex("ccbebda2bfff")  # "RDC1E"
    # A pre-existing broken build could still point the RDC slots at that table.
    for slot in fi._find_slots(source)[0x41803A]:
        struct.pack_into("<I", rom, slot, ROM_BASE + 0x41803A)

    fi.apply(rom, source)
    assert _all_slots_correct(rom, source)


def test_occupation_guard_refuses_live_data():
    rom = _build_synthetic_rom()
    source = bytes(rom)
    # Poison the reserved region with non-0xFF live-looking data.
    rom[fi.FLOOR_STR_OFFSET] = 0x42
    with pytest.raises(SystemExit):
        fi.apply(rom, source)


def test_aborts_when_base_layout_missing_floor_pointers():
    rom = bytearray(b"\x00" * ROM_SIZE)
    rom[0xB2] = 0x96
    rom[fi.FLOOR_STR_OFFSET:fi.FLOOR_STR_OFFSET + 0x100] = b"\xFF" * 0x100
    with pytest.raises(SystemExit):
        fi.apply(rom, bytes(rom))  # no pointer tables -> abort loudly


# --- End-to-end wiring against the real built ROM (skipped if absent) --------

FR_ROM = REPO_ROOT / "output/roms/GenedRom-fr.gba"
EN_ROM = REPO_ROOT / "input/roms/englishrom.gba"


@pytest.mark.rom
@pytest.mark.skipif(
    not (FR_ROM.exists() and EN_ROM.exists()), reason="built ROMs not present"
)
def test_built_fr_rom_has_all_floors_translated():
    source = EN_ROM.read_bytes()
    rom = FR_ROM.read_bytes()
    for en_off, slots in fi._find_slots(source).items():
        assert slots, f"no floor pointer for {en_off:#x}"
        for slot in slots:
            ptr = struct.unpack_from("<I", rom, slot)[0]
            assert _decode_at(rom, ptr) == fi.FR_LABELS[en_off], (
                f"slot {slot:#x} not translated in built ROM"
            )
