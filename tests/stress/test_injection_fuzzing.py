"""Stress: Injection fuzzing — edge-case text injection into ROM bytearray.

Operates entirely in memory (no mGBA required). Tests max-length texts,
forced relocation of all entries, empty strings, control-code-only
strings, and FD code preservation.
"""

import re
import struct

import pytest

from src.core.text_codec import POKEMON_TERMINATOR, TextDecoder, TextEncoder
from src.core.text_reinserter import FreeSpaceAllocator, SmartReinserter
from tests.stress.conftest import (
    GBA_ROM_BASE,
    ROM_SIZE,
    make_fake_rom,
    read_pointer,
    write_pointer,
)

pytestmark = [pytest.mark.stress]

HEX_TOKEN_RE = re.compile(r"<0x[0-9A-Fa-f]{2}>")

SLOT_OFFSET = 0x100000
SLOT_SIZE = 30
NUM_SLOTS = 200
POINTER_TABLE_START = 0x50000
FREE_SPACE_START = 0x1800000


def _build_rom_with_slots():
    rom = make_fake_rom()
    rom[FREE_SPACE_START:] = bytearray([0xFF] * (ROM_SIZE - FREE_SPACE_START))
    entries = []
    for i in range(NUM_SLOTS):
        text_offset = SLOT_OFFSET + i * SLOT_SIZE
        ptr_offset = POINTER_TABLE_START + i * 4
        original = TextEncoder.encode_pokemon(f"Entry {i:03d}")
        for j, b in enumerate(original):
            rom[text_offset + j] = b
        write_pointer(rom, ptr_offset, text_offset)
        entries.append({
            "offset": text_offset,
            "original_length": len(original) - 1,
            "encoding": "pokemon",
            "pointer_offsets": [ptr_offset],
        })
    return rom, entries


class TestMaxLengthInjection:
    """Inject texts at maximum slot capacity."""

    def test_inject_max_length_texts(self):
        rom, entries = _build_rom_with_slots()
        reinserter = SmartReinserter(rom, allow_relocate=True)

        for entry in entries:
            max_chars = entry["original_length"]
            text = "A" * max_chars
            success = reinserter.reinsert_text({
                **entry,
                "translation": text,
            })
            assert success, f"Failed at offset 0x{entry['offset']:08X}"

        report = reinserter.get_report()
        assert report["statistics"]["failed"] == 0

    def test_inject_exactly_max_length_fits_in_slot(self):
        rom, entries = _build_rom_with_slots()
        reinserter = SmartReinserter(rom, allow_relocate=False)

        entry = entries[0]
        text = "B" * entry["original_length"]
        encoded = TextEncoder.encode_pokemon(text)
        assert len(encoded) == entry["original_length"] + 1
        success = reinserter.reinsert_text({**entry, "translation": text})
        assert success


class TestForcedRelocationAll:
    """Force relocation of every entry by injecting oversized texts."""

    def test_relocate_all_entries(self):
        rom, entries = _build_rom_with_slots()
        reinserter = SmartReinserter(rom, allow_relocate=True)

        for entry in entries:
            text = "Z" * (entry["original_length"] + 20)
            success = reinserter.reinsert_text({
                **entry,
                "translation": text,
            })
            assert success, f"Relocation failed at 0x{entry['offset']:08X}"

        report = reinserter.get_report()
        assert report["statistics"]["relocated"] == NUM_SLOTS
        assert report["statistics"]["relocation_failed"] == 0

    def test_relocated_pointers_valid(self):
        rom, entries = _build_rom_with_slots()
        reinserter = SmartReinserter(rom, allow_relocate=True)

        for entry in entries:
            text = "W" * (entry["original_length"] + 20)
            reinserter.reinsert_text({**entry, "translation": text})
        reinserter.flush_relocations()

        for entry in entries:
            for ptr_off in entry["pointer_offsets"]:
                target = read_pointer(rom, ptr_off)
                assert target is not None, (
                    f"Pointer at 0x{ptr_off:08X} is invalid after relocation"
                )
                assert target >= FREE_SPACE_START, (
                    f"Relocated pointer at 0x{ptr_off:08X} points to "
                    f"0x{target:08X}, expected >= 0x{FREE_SPACE_START:08X}"
                )

    def test_relocated_text_terminated(self):
        rom, entries = _build_rom_with_slots()
        reinserter = SmartReinserter(rom, allow_relocate=True)

        for entry in entries:
            text = "Q" * (entry["original_length"] + 15)
            reinserter.reinsert_text({**entry, "translation": text})
        reinserter.flush_relocations()

        for entry in entries:
            ptr_off = entry["pointer_offsets"][0]
            target = read_pointer(rom, ptr_off)
            assert target is not None
            encoded = TextEncoder.encode_pokemon("Q" * (entry["original_length"] + 15))
            end = target + len(encoded) - 1
            assert rom[end] == POKEMON_TERMINATOR, (
                f"String at 0x{target:08X} not terminated by 0xFF at byte {end}"
            )


class TestEdgeCaseStrings:
    """Inject boundary-condition strings: empty, control-only, single char."""

    def test_inject_empty_string(self):
        rom, entries = _build_rom_with_slots()
        reinserter = SmartReinserter(rom)
        entry = entries[0]
        success = reinserter.reinsert_text({**entry, "translation": ""})
        assert success
        assert rom[entry["offset"]] == POKEMON_TERMINATOR

    def test_inject_single_character(self):
        rom, entries = _build_rom_with_slots()
        reinserter = SmartReinserter(rom)
        entry = entries[1]
        success = reinserter.reinsert_text({**entry, "translation": "X"})
        assert success

    def test_inject_control_codes_only_fd(self):
        rom, entries = _build_rom_with_slots()
        reinserter = SmartReinserter(rom)
        entry = entries[2]
        text = "<0xFD><0xFD><0xFD>"
        success = reinserter.reinsert_text({**entry, "translation": text})
        assert success
        offset = entry["offset"]
        assert rom[offset] == 0xFD
        assert rom[offset + 1] == 0xFD
        assert rom[offset + 2] == 0xFD
        assert rom[offset + 3] == POKEMON_TERMINATOR

    def test_inject_control_codes_only_fc(self):
        rom, entries = _build_rom_with_slots()
        reinserter = SmartReinserter(rom)
        entry = entries[3]
        text = "<0xFC><0xFC>"
        success = reinserter.reinsert_text({**entry, "translation": text})
        assert success
        offset = entry["offset"]
        assert rom[offset] == 0xFC
        assert rom[offset + 1] == 0xFC
        assert rom[offset + 2] == POKEMON_TERMINATOR


class TestFDCodePreservation:
    """Verify FD control codes survive injection intact."""

    FD_TEXTS = [
        "Hi<0xFD>Go",
        "<0xFD>Start",
        "End<0xFD>",
        "<0xFD><0xFD>Dbl",
        "A<0xFD>B<0xFD>C",
    ]

    def test_fd_codes_preserved_in_slot(self):
        rom, entries = _build_rom_with_slots()
        reinserter = SmartReinserter(rom)

        for i, text in enumerate(self.FD_TEXTS):
            entry = entries[10 + i]
            success = reinserter.reinsert_text({**entry, "translation": text})
            assert success, f"FD injection failed for: {text}"

            offset = entry["offset"]
            encoded = TextEncoder.encode_pokemon(text)
            fd_count_expected = encoded[:-1].count(0xFD)
            fd_count_actual = 0
            for j in range(len(encoded) - 1):
                if rom[offset + j] == 0xFD:
                    fd_count_actual += 1
            assert fd_count_actual == fd_count_expected, (
                f"FD count mismatch for '{text}': "
                f"expected {fd_count_expected}, got {fd_count_actual}"
            )

    def test_fd_codes_preserved_after_relocation(self):
        rom, entries = _build_rom_with_slots()
        reinserter = SmartReinserter(rom, allow_relocate=True)

        text = "A" * 40 + "<0xFD>B<0xFD>C"
        entry = entries[20]
        success = reinserter.reinsert_text({**entry, "translation": text})
        assert success
        reinserter.flush_relocations()

        ptr_off = entry["pointer_offsets"][0]
        target = read_pointer(rom, ptr_off)
        assert target is not None

        encoded = TextEncoder.encode_pokemon(text)
        fd_expected = sum(1 for b in encoded[:-1] if b == 0xFD)
        fd_actual = sum(1 for j in range(len(encoded) - 1) if rom[target + j] == 0xFD)
        assert fd_actual == fd_expected

    def test_fd_round_trip_encode_decode(self):
        for text in self.FD_TEXTS:
            encoded = TextEncoder.encode_pokemon(text)
            fd_in_encoded = sum(1 for b in encoded[:-1] if b == 0xFD)
            fd_in_source = text.count("<0xFD>")
            assert fd_in_encoded == fd_in_source, (
                f"Encoder dropped FD codes in '{text}': "
                f"expected {fd_in_source}, got {fd_in_encoded}"
            )


class TestBulkInjectionIntegrity:
    """Inject many entries and verify global ROM integrity."""

    def test_bulk_inject_200_entries_no_overlap(self):
        rom, entries = _build_rom_with_slots()
        reinserter = SmartReinserter(rom, allow_relocate=True)

        for i, entry in enumerate(entries):
            length = (i % 25) + 5
            text = chr(ord("A") + (i % 26)) * length
            reinserter.reinsert_text({**entry, "translation": text})

        report = reinserter.get_report()
        assert report["statistics"]["failed"] == 0

        written_ranges = []
        for entry in entries:
            ptr_off = entry["pointer_offsets"][0]
            target = read_pointer(rom, ptr_off)
            if target is not None and target >= FREE_SPACE_START:
                end_scan = target
                while end_scan < len(rom) and rom[end_scan] != POKEMON_TERMINATOR:
                    end_scan += 1
                written_ranges.append((target, end_scan + 1))

        written_ranges.sort()
        for i in range(len(written_ranges) - 1):
            _, end_a = written_ranges[i]
            start_b, _ = written_ranges[i + 1]
            assert end_a <= start_b, (
                f"Overlap detected: entry ending at 0x{end_a:08X} "
                f"overlaps with entry starting at 0x{start_b:08X}"
            )
