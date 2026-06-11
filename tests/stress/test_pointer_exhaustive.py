"""Stress: Exhaustive pointer validation after injection.

For every relocated entry, verify ALL pointers that reference it have
been updated to the new address. Detect orphan pointers and overlaps.

Does NOT scan the entire ROM for pointers — only uses known pointer
locations from the extraction data. No mGBA required.
"""

import struct

import pytest

from src.core.text_codec import POKEMON_TERMINATOR, TextEncoder
from src.core.text_reinserter import SmartReinserter
from tests.stress.conftest import (
    GBA_ROM_BASE,
    ROM_SIZE,
    make_fake_rom,
    read_pointer,
    write_pointer,
)

pytestmark = [pytest.mark.stress]

TEXT_REGION_START = 0x100000
POINTER_TABLE_START = 0x50000
FREE_SPACE_START = 0x600000
NUM_ENTRIES = 500
SLOT_SIZE = 40
POINTERS_PER_ENTRY = 3


def _build_multi_pointer_rom():
    rom = make_fake_rom()
    rom[FREE_SPACE_START:] = bytearray([0xFF] * (ROM_SIZE - FREE_SPACE_START))
    entries = []
    ptr_idx = 0
    for i in range(NUM_ENTRIES):
        text_offset = TEXT_REGION_START + i * SLOT_SIZE
        original = TextEncoder.encode_pokemon(f"Text {i:04d}")
        for j, b in enumerate(original):
            rom[text_offset + j] = b

        ptr_offsets = []
        for p in range(POINTERS_PER_ENTRY):
            ptr_off = POINTER_TABLE_START + ptr_idx * 4
            write_pointer(rom, ptr_off, text_offset)
            ptr_offsets.append(ptr_off)
            ptr_idx += 1

        entries.append({
            "offset": text_offset,
            "original_length": len(original) - 1,
            "encoding": "pokemon",
            "pointer_offsets": ptr_offsets,
        })
    return rom, entries


def _inject_all_oversized(rom, entries):
    reinserter = SmartReinserter(rom, allow_relocate=True)
    for entry in entries:
        text = "X" * (entry["original_length"] + 30)
        reinserter.reinsert_text({**entry, "translation": text})
    return reinserter.get_report()


class TestAllPointersUpdated:
    """After relocation, every known pointer must point to the new address."""

    def test_all_pointers_point_to_relocated_address(self):
        rom, entries = _build_multi_pointer_rom()
        _inject_all_oversized(rom, entries)

        mismatches = []
        for entry in entries:
            targets = set()
            for ptr_off in entry["pointer_offsets"]:
                target = read_pointer(rom, ptr_off)
                if target is not None:
                    targets.add(target)

            if len(targets) > 1:
                mismatches.append({
                    "offset": f"0x{entry['offset']:08X}",
                    "distinct_targets": [f"0x{t:08X}" for t in sorted(targets)],
                })

        assert len(mismatches) == 0, (
            f"{len(mismatches)} entries have inconsistent pointer targets: "
            f"{mismatches[:5]}"
        )

    def test_no_pointer_points_to_original_after_relocation(self):
        rom, entries = _build_multi_pointer_rom()
        _inject_all_oversized(rom, entries)

        stale = []
        for entry in entries:
            original_offset = entry["offset"]
            for ptr_off in entry["pointer_offsets"]:
                target = read_pointer(rom, ptr_off)
                if target == original_offset:
                    stale.append(f"0x{ptr_off:08X} -> 0x{original_offset:08X}")

        assert len(stale) == 0, (
            f"{len(stale)} pointers still point to original address: {stale[:10]}"
        )

    def test_total_pointers_updated_equals_expected(self):
        rom, entries = _build_multi_pointer_rom()
        report = _inject_all_oversized(rom, entries)
        assert report["statistics"]["relocated"] == NUM_ENTRIES


class TestOrphanPointerDetection:
    """Detect pointers that land in free space but not at a string start."""

    def test_no_orphan_pointers_in_free_space(self):
        rom, entries = _build_multi_pointer_rom()
        _inject_all_oversized(rom, entries)

        string_starts = set()
        for entry in entries:
            ptr_off = entry["pointer_offsets"][0]
            target = read_pointer(rom, ptr_off)
            if target is not None and target >= FREE_SPACE_START:
                string_starts.add(target)

        orphans = []
        for entry in entries:
            for ptr_off in entry["pointer_offsets"]:
                target = read_pointer(rom, ptr_off)
                if target is None:
                    continue
                if target >= FREE_SPACE_START and target not in string_starts:
                    orphans.append(f"0x{ptr_off:08X} -> 0x{target:08X}")

        assert len(orphans) == 0, (
            f"{len(orphans)} orphan pointers detected: {orphans[:10]}"
        )


class TestStringTermination:
    """Every pointer must land on a 0xFF-terminated string."""

    def test_all_relocated_strings_terminated(self):
        rom, entries = _build_multi_pointer_rom()
        _inject_all_oversized(rom, entries)

        unterminated = []
        for entry in entries:
            ptr_off = entry["pointer_offsets"][0]
            target = read_pointer(rom, ptr_off)
            if target is None:
                continue

            found_terminator = False
            scan_limit = min(target + 1000, len(rom))
            for pos in range(target, scan_limit):
                if rom[pos] == POKEMON_TERMINATOR:
                    found_terminator = True
                    break

            if not found_terminator:
                unterminated.append(f"0x{target:08X}")

        assert len(unterminated) == 0, (
            f"{len(unterminated)} strings lack 0xFF terminator: {unterminated[:10]}"
        )


class TestPointerEntryOverlap:
    """No entry data should overlap a pointer location (4-byte window)."""

    def test_no_entry_overlaps_pointer_location(self):
        rom, entries = _build_multi_pointer_rom()
        _inject_all_oversized(rom, entries)

        all_ptr_locations = set()
        for entry in entries:
            for ptr_off in entry["pointer_offsets"]:
                all_ptr_locations.add(ptr_off)

        overlaps = []
        for entry in entries:
            ptr_off = entry["pointer_offsets"][0]
            target = read_pointer(rom, ptr_off)
            if target is None:
                continue

            end = target
            scan_limit = min(target + 1000, len(rom))
            for pos in range(target, scan_limit):
                if rom[pos] == POKEMON_TERMINATOR:
                    end = pos + 1
                    break

            for ptr_loc in all_ptr_locations:
                if target < ptr_loc + 4 and ptr_loc < end:
                    overlaps.append(
                        f"entry [0x{target:08X}-0x{end:08X}] "
                        f"overlaps ptr at 0x{ptr_loc:08X}"
                    )

        assert len(overlaps) == 0, (
            f"{len(overlaps)} pointer/entry overlaps: {overlaps[:10]}"
        )


class TestMultiplePointersPerEntry:
    """Entries with multiple pointers must have ALL pointers agree."""

    def test_triple_pointers_all_consistent(self):
        rom, entries = _build_multi_pointer_rom()
        _inject_all_oversized(rom, entries)

        inconsistent = []
        for entry in entries:
            targets = []
            for ptr_off in entry["pointer_offsets"]:
                t = read_pointer(rom, ptr_off)
                targets.append(t)

            unique = set(targets)
            if None in unique:
                unique.discard(None)
            if len(unique) != 1:
                inconsistent.append({
                    "original": f"0x{entry['offset']:08X}",
                    "targets": [f"0x{t:08X}" if t else "None" for t in targets],
                })

        assert len(inconsistent) == 0, (
            f"{len(inconsistent)} entries have inconsistent multi-pointers: "
            f"{inconsistent[:5]}"
        )

    def test_pointer_count_preserved(self):
        rom, entries = _build_multi_pointer_rom()
        _inject_all_oversized(rom, entries)

        for entry in entries:
            valid_count = sum(
                1 for ptr_off in entry["pointer_offsets"]
                if read_pointer(rom, ptr_off) is not None
            )
            assert valid_count == POINTERS_PER_ENTRY, (
                f"Entry 0x{entry['offset']:08X}: only {valid_count}/"
                f"{POINTERS_PER_ENTRY} pointers valid"
            )
