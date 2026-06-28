"""Stress: Free-space exhaustion and fragmentation.

Simulate injection when free space is nearly depleted or heavily
fragmented. Verify clean failure (no corruption) when space runs out
and that the bump allocator never re-uses already-claimed space.

No mGBA required — operates entirely on in-memory bytearrays.
"""

import struct

import pytest

from src.core.text_codec import POKEMON_TERMINATOR, TextEncoder
from src.core.text_reinserter import FreeSpaceAllocator, SmartReinserter
from tests.stress.conftest import (
    GBA_ROM_BASE,
    ROM_SIZE,
    make_fake_rom,
    read_pointer,
    write_pointer,
)

pytestmark = [pytest.mark.stress]

SLOT_OFFSET = 0x100000
SLOT_SIZE = 30
POINTER_TABLE_START = 0x50000


def _make_entry(rom, index, text_offset, ptr_offset):
    original = TextEncoder.encode_pokemon(f"T{index:03d}")
    for j, b in enumerate(original):
        rom[text_offset + j] = b
    write_pointer(rom, ptr_offset, text_offset)
    return {
        "offset": text_offset,
        "original_length": len(original) - 1,
        "encoding": "pokemon",
        "pointer_offsets": [ptr_offset],
    }


class TestNearlyExhaustedSpace:
    """Inject when only a tiny free block remains."""

    def test_last_allocation_succeeds(self):
        rom = make_fake_rom()
        free_start = ROM_SIZE - 128
        rom[free_start:] = bytearray([0xFF] * 128)

        entry = _make_entry(rom, 0, SLOT_OFFSET, POINTER_TABLE_START)
        reinserter = SmartReinserter(rom, allow_relocate=True)
        text = "A" * (entry["original_length"] + 20)
        encoded = TextEncoder.encode_pokemon(text)
        assert len(encoded) < 128

        success = reinserter.reinsert_text({**entry, "translation": text})
        assert success

    def test_allocation_fails_cleanly_when_space_gone(self):
        rom = make_fake_rom()
        free_start = ROM_SIZE - 32
        rom[free_start:] = bytearray([0xFF] * 32)

        entry = _make_entry(rom, 0, SLOT_OFFSET, POINTER_TABLE_START)
        reinserter = SmartReinserter(rom, allow_relocate=True)

        text = "B" * 200
        reinserter.reinsert_text({**entry, "translation": text})

        report = reinserter.get_report()
        assert report["statistics"]["relocation_failed"] == 1
        assert report["statistics"]["failed"] == 0

    def test_no_corruption_on_failed_allocation(self):
        rom = make_fake_rom()
        free_start = ROM_SIZE - 16
        rom[free_start:] = bytearray([0xFF] * 16)

        original_snapshot = bytes(rom[SLOT_OFFSET:SLOT_OFFSET + SLOT_SIZE])
        entry = _make_entry(rom, 0, SLOT_OFFSET, POINTER_TABLE_START)
        ptr_before = read_pointer(rom, POINTER_TABLE_START)

        reinserter = SmartReinserter(rom, allow_relocate=True)
        text = "C" * 500
        reinserter.reinsert_text({**entry, "translation": text})

        ptr_after = read_pointer(rom, POINTER_TABLE_START)
        assert ptr_after == ptr_before, (
            "Pointer was modified despite failed allocation"
        )


class TestFragmentedFreeSpace:
    """Free space split into many small blocks."""

    def _make_fragmented_rom(self, block_size=64, gap_size=32, num_blocks=50):
        rom = make_fake_rom()
        start = 0x1000000
        for i in range(num_blocks):
            block_start = start + i * (block_size + gap_size)
            if block_start + block_size > ROM_SIZE:
                break
            rom[block_start:block_start + block_size] = bytearray([0xFF] * block_size)
        return rom, start

    def test_allocations_fit_in_fragments(self):
        rom, _ = self._make_fragmented_rom(block_size=64, gap_size=32, num_blocks=50)
        entries = []
        for i in range(30):
            entry = _make_entry(
                rom, i,
                SLOT_OFFSET + i * SLOT_SIZE,
                POINTER_TABLE_START + i * 4,
            )
            entries.append(entry)

        reinserter = SmartReinserter(rom, allow_relocate=True)
        successes = 0
        for entry in entries:
            text = "D" * (entry["original_length"] + 20)
            encoded = TextEncoder.encode_pokemon(text)
            if len(encoded) <= 64:
                if reinserter.reinsert_text({**entry, "translation": text}):
                    successes += 1

        assert successes > 0, "No entries fit in fragmented blocks"

    def test_large_text_fails_in_small_fragments(self):
        rom, _ = self._make_fragmented_rom(block_size=32, gap_size=32, num_blocks=20)
        entry = _make_entry(rom, 0, SLOT_OFFSET, POINTER_TABLE_START)

        reinserter = SmartReinserter(rom, allow_relocate=True)
        text = "E" * 200
        reinserter.reinsert_text({**entry, "translation": text})
        reinserter.flush_relocations()
        assert reinserter.stats["relocation_failed"] == 1

    def test_fragmented_no_data_corruption(self):
        rom, _ = self._make_fragmented_rom(block_size=48, gap_size=16, num_blocks=30)
        sentinel_offset = 0x200000
        sentinel = b"SENTINEL_DATA_UNTOUCHED"
        rom[sentinel_offset:sentinel_offset + len(sentinel)] = sentinel

        entries = []
        for i in range(20):
            entry = _make_entry(
                rom, i,
                SLOT_OFFSET + i * SLOT_SIZE,
                POINTER_TABLE_START + i * 4,
            )
            entries.append(entry)

        reinserter = SmartReinserter(rom, allow_relocate=True)
        for entry in entries:
            text = "F" * (entry["original_length"] + 10)
            reinserter.reinsert_text({**entry, "translation": text})

        actual = bytes(rom[sentinel_offset:sentinel_offset + len(sentinel)])
        assert actual == sentinel, "Sentinel data was corrupted during injection"


class TestBumpAllocatorNoReuse:
    """The bump allocator must not hand out the same region twice."""

    def test_sequential_allocations_never_overlap(self):
        rom = make_fake_rom()
        free_start = 0x600000
        rom[free_start:free_start + 0x100000] = bytearray([0xFF] * 0x100000)

        allocator = FreeSpaceAllocator(rom, min_block=16, start_offset=free_start)

        allocated = []
        for _ in range(100):
            addr = allocator.allocate(64)
            if addr is None:
                break
            allocated.append((addr, addr + 64))

        assert len(allocated) > 10, "Too few allocations succeeded"

        for i in range(len(allocated)):
            for j in range(i + 1, len(allocated)):
                start_a, end_a = allocated[i]
                start_b, end_b = allocated[j]
                assert end_a <= start_b or end_b <= start_a, (
                    f"Overlap: [{start_a:#x},{end_a:#x}) and [{start_b:#x},{end_b:#x})"
                )

    def test_allocator_returns_none_when_exhausted(self):
        rom = make_fake_rom()
        free_start = ROM_SIZE - 256
        rom[free_start:] = bytearray([0xFF] * 256)

        allocator = FreeSpaceAllocator(rom, min_block=16, start_offset=free_start)

        results = []
        for _ in range(20):
            results.append(allocator.allocate(64))

        non_none = [r for r in results if r is not None]
        assert len(non_none) <= 4, f"Too many allocations from 256 bytes: {len(non_none)}"
        assert results[-1] is None, "Allocator should return None when exhausted"

    def test_allocator_skips_non_padding_bytes(self):
        # Blocks must be at least MIN_FREE_RUN to count as free space.
        rom = make_fake_rom()
        free_start = 0x800000
        block_size = FreeSpaceAllocator.MIN_FREE_RUN * 2
        rom[free_start:free_start + block_size] = bytearray([0xFF] * block_size)
        rom[free_start + block_size:free_start + block_size + 64] = bytearray([0x42] * 64)
        rom[free_start + block_size + 64:free_start + block_size + 64 + block_size] = (
            bytearray([0xFF] * block_size)
        )

        allocator = FreeSpaceAllocator(rom, start_offset=free_start)

        size = block_size - 64
        addr1 = allocator.allocate(size)
        assert addr1 is not None
        assert free_start <= addr1 < free_start + block_size

        addr2 = allocator.allocate(size)
        assert addr2 is not None
        gap_end = free_start + block_size + 64
        assert addr2 >= gap_end, (
            f"Second allocation at 0x{addr2:08X} overlaps non-padding region"
        )


class TestGracefulDegradation:
    """When space is exhausted mid-batch, already-written entries stay valid."""

    def test_partial_batch_leaves_early_entries_intact(self):
        rom = make_fake_rom()
        free_start = ROM_SIZE - (FreeSpaceAllocator.MIN_FREE_RUN + 512)
        rom[free_start:] = bytearray([0xFF] * (ROM_SIZE - free_start))

        entries = []
        for i in range(20):
            entry = _make_entry(
                rom, i,
                SLOT_OFFSET + i * SLOT_SIZE,
                POINTER_TABLE_START + i * 4,
            )
            entries.append(entry)

        reinserter = SmartReinserter(rom, allow_relocate=True)
        for i, entry in enumerate(entries):
            # Each string must be distinct: identical relocated strings are
            # deduplicated (they share a single copy), which would let the whole
            # batch fit and defeat the exhaustion scenario this test exercises.
            text = "G" * 299 + chr(ord("A") + i)
            reinserter.reinsert_text({**entry, "translation": text})
        reinserter.flush_relocations()

        # Relocations are deferred: success is determined after the flush by
        # whether each entry's pointer was repointed into free space.
        succeeded = []
        failed = []
        for i, entry in enumerate(entries):
            target = read_pointer(rom, entry["pointer_offsets"][0])
            if target is not None and target >= free_start:
                succeeded.append(i)
            else:
                failed.append(i)
        assert len(succeeded) > 0, "No entries succeeded"
        assert len(failed) > 0, "All entries succeeded — space wasn't tight enough"

        for i in succeeded:
            entry = entries[i]
            ptr_off = entry["pointer_offsets"][0]
            target = read_pointer(rom, ptr_off)
            assert target is not None, (
                f"Successful entry {i} has invalid pointer"
            )
            assert target >= free_start, (
                f"Successful entry {i} pointer doesn't point to free space"
            )
            found_term = False
            for pos in range(target, min(target + 400, len(rom))):
                if rom[pos] == POKEMON_TERMINATOR:
                    found_term = True
                    break
            assert found_term, f"Entry {i} at 0x{target:08X} has no terminator"
