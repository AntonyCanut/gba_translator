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
    # The place-bound floor labels (elevator menus, Cube emerald list) live at
    # pinned slots, so the fixture has to mirror the real base-ROM layout.
    for slot, (en_cell, _label) in fi.EXTRA_SLOTS.items():
        struct.pack_into("<I", rom, slot, ROM_BASE + en_cell)
    return rom


TOTAL_TABLE_SLOTS = len(POINTER_TABLE_OFFSETS) * len(fi.FR_LABELS)  # 3 x 15
TOTAL_SLOTS = TOTAL_TABLE_SLOTS + len(fi.EXTRA_SLOTS)


def _all_slots_correct(rom: bytes, source: bytes) -> bool:
    for en_off, slots in fi._find_slots(source).items():
        for slot in slots:
            ptr = struct.unpack_from("<I", rom, slot)[0]
            if _decode_at(rom, ptr) != fi.FR_LABELS[en_off]:
                return False
    for slot, (_en_cell, label) in fi.EXTRA_SLOTS.items():
        ptr = struct.unpack_from("<I", rom, slot)[0]
        if _decode_at(rom, ptr) != label:
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

    # 3 tables x 15 cells + every pinned place-bound slot, all repointed.
    assert patched == TOTAL_SLOTS
    assert _all_slots_correct(rom, source)
    # No slot may still resolve to an English residue ("1F", "B1F"…).
    resolved = [
        struct.unpack_from("<I", rom, slot)[0]
        for slots in fi._find_slots(source).values()
        for slot in slots
    ]
    resolved += [struct.unpack_from("<I", rom, slot)[0] for slot in fi.EXTRA_SLOTS]
    for ptr in resolved:
        assert not _decode_at(rom, ptr).endswith("F")


def test_apply_is_idempotent():
    rom = _build_synthetic_rom()
    source = bytes(rom)
    assert fi.apply(rom, source) == TOTAL_SLOTS
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


def test_place_bound_labels_are_repointed_to_french():
    """Elevator menus and the Cube emerald list show floors next to a place.

    They are served by their own cells (not the 0x41803A table), which is why
    #100 kept reporting untranslated floors after the pop-up itself was fixed.
    """
    rom = _build_synthetic_rom()
    source = bytes(rom)
    fi.apply(rom, source)

    for slot, (_en_cell, label) in fi.EXTRA_SLOTS.items():
        ptr = struct.unpack_from("<I", rom, slot)[0]
        assert _decode_at(rom, ptr) == label, f"slot {slot:#x} still English"

    # Every French label reused here must come from the reserved region, so the
    # patch never allocates a second copy that a rebuild could reshuffle.
    end = fi.FLOOR_STR_OFFSET + 0x100
    for slot in fi.EXTRA_SLOTS:
        ptr = struct.unpack_from("<I", rom, slot)[0] - ROM_BASE
        assert fi.FLOOR_STR_OFFSET <= ptr < end


def test_extra_slots_only_reference_known_floor_labels():
    """A typo in EXTRA_SLOTS must not silently invent an unreserved label."""
    assert set(label for _cell, label in fi.EXTRA_SLOTS.values()) <= set(
        fi.FR_LABELS.values()
    )


def test_aborts_when_a_pinned_slot_moved():
    rom = _build_synthetic_rom()
    source = bytearray(rom)
    moved = next(iter(fi.EXTRA_SLOTS))
    struct.pack_into("<I", source, moved, ROM_BASE + 0x123456)
    with pytest.raises(SystemExit):
        fi.apply(rom, bytes(source))


def test_lookalike_pointer_in_sample_data_is_left_alone():
    """0xB21C48 reads as a pointer to the "B2F" cell but is graphics/sample data.

    Repointing it would corrupt unrelated bytes, so the patch must work from the
    pinned slot list rather than from a byte-pattern scan.
    """
    assert 0xB21C48 not in fi.EXTRA_SLOTS
    rom = _build_synthetic_rom()
    source = bytearray(rom)
    struct.pack_into("<I", source, 0xB21C48, ROM_BASE + 0x1F6F602)
    rom[0xB21C48:0xB21C4C] = source[0xB21C48:0xB21C4C]
    fi.apply(rom, bytes(source))
    assert struct.unpack_from("<I", rom, 0xB21C48)[0] == ROM_BASE + 0x1F6F602


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


@pytest.mark.rom
@pytest.mark.skipif(
    not (FR_ROM.exists() and EN_ROM.exists()), reason="built ROMs not present"
)
def test_built_fr_rom_has_place_bound_floors_translated():
    """Elevator menus and the Cube emerald list must be French in the artifact."""
    source = EN_ROM.read_bytes()
    rom = FR_ROM.read_bytes()
    for slot, (en_cell, label) in fi.EXTRA_SLOTS.items():
        assert struct.unpack_from("<I", source, slot)[0] == ROM_BASE + en_cell, (
            f"base ROM layout moved at slot {slot:#x}"
        )
        ptr = struct.unpack_from("<I", rom, slot)[0]
        assert _decode_at(rom, ptr) == label, (
            f"slot {slot:#x} still shows an English floor in the built ROM"
        )
