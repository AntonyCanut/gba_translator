"""Benchmark tests for free-space allocation performance."""

import time

import pytest

from src.core.text_reinserter import FreeSpaceAllocator

pytestmark = pytest.mark.benchmark


class TestAllocationSpeed:
    """Measure allocation throughput."""

    def test_1000_allocations_under_1ms_each(self, rom_32mb, timer):
        allocator = FreeSpaceAllocator(rom_32mb, min_block=16)

        timings = []
        for _ in range(1000):
            start = time.perf_counter()
            result = allocator.allocate(32)
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
            if result is None:
                break

        max_time = max(timings)
        avg_time = sum(timings) / len(timings)
        print(f"  [allocation] avg={avg_time*1000:.3f}ms  max={max_time*1000:.3f}ms")

        assert max_time < 0.001, f"Slowest allocation took {max_time*1000:.3f}ms (limit 1ms)"

    def test_allocation_total_time(self, rom_32mb, timer):
        allocator = FreeSpaceAllocator(rom_32mb, min_block=16)

        with timer("1000 allocations total") as t:
            for _ in range(1000):
                result = allocator.allocate(32)
                if result is None:
                    break

        assert t["elapsed"] < 1, f"1000 allocations took {t['elapsed']:.2f}s"

    def test_varying_sizes(self, rom_32mb, timer):
        allocator = FreeSpaceAllocator(rom_32mb, min_block=8)
        sizes = [8, 16, 32, 64, 128, 256, 512, 1024]

        with timer("varying-size allocations") as t:
            for size in sizes:
                for _ in range(100):
                    result = allocator.allocate(size)
                    if result is None:
                        break

        assert t["elapsed"] < 2


class TestFragmentation:
    """Measure fragmentation effects on allocation performance."""

    def test_fragmentation_after_many_allocations(self, rom_with_data, timer):
        allocator = FreeSpaceAllocator(rom_with_data, min_block=8)

        initial_blocks = len(allocator.blocks)
        allocated_count = 0

        with timer("500 allocations on fragmented ROM") as t:
            for _ in range(500):
                result = allocator.allocate(64)
                if result is None:
                    break
                allocated_count += 1

        remaining_blocks = sum(1 for b in allocator.blocks if b[1] >= 8)
        print(f"  [fragmentation] initial_blocks={initial_blocks} "
              f"allocated={allocated_count} remaining={remaining_blocks}")

        assert t["elapsed"] < 5, f"Fragmented allocation took {t['elapsed']:.2f}s"

    def test_small_block_saturation(self, timer):
        """Allocate until no space remains; measure how gracefully it degrades."""
        rom = bytearray(b"\xFF" * (64 * 1024))  # 64 KB
        allocator = FreeSpaceAllocator(rom, min_block=8)

        count = 0
        with timer("allocate until full") as t:
            while True:
                result = allocator.allocate(128)
                if result is None:
                    break
                count += 1

        print(f"  [saturation] allocated {count} blocks before exhaustion")
        assert t["elapsed"] < 2


class TestScanPerformance:
    """Measure the initial free-space scan."""

    def test_scan_32mb_rom(self, timer):
        rom = bytearray(b"\xFF" * (32 * 1024 * 1024))

        with timer("scan 32MB all-free ROM") as t:
            allocator = FreeSpaceAllocator(rom, min_block=16)

        assert t["elapsed"] < 5, f"Scan took {t['elapsed']:.2f}s"
        assert len(allocator.blocks) >= 1

    def test_scan_mixed_rom(self, rom_with_data, timer):
        with timer("scan 32MB mixed ROM") as t:
            allocator = FreeSpaceAllocator(rom_with_data, min_block=16)

        assert t["elapsed"] < 5, f"Scan took {t['elapsed']:.2f}s"
        assert len(allocator.blocks) >= 1
