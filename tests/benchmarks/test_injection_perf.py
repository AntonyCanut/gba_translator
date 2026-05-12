"""Benchmark tests for text injection performance."""

import time

import pytest

from src.core.text_reinserter import SmartReinserter
from src.core.text_codec import TextEncoder

pytestmark = pytest.mark.benchmark


class TestBatchInjection:
    """Measure batch injection throughput."""

    def test_batch_injection_500_entries(
        self, rom_32mb, sample_translations_medium, timer
    ):
        rom = bytearray(rom_32mb)
        reinserter = SmartReinserter(rom)

        with timer("batch 500 entries") as t:
            reinserter.reinsert_all(sample_translations_medium)

        report = reinserter.get_report()
        assert report["statistics"]["successful"] == 500
        assert t["elapsed"] < 30, f"Batch injection took {t['elapsed']:.2f}s (limit 30s)"

    def test_batch_injection_5000_entries(
        self, rom_32mb, sample_translations_large, timer
    ):
        rom = bytearray(rom_32mb)
        reinserter = SmartReinserter(rom)

        with timer("batch 5000 entries") as t:
            reinserter.reinsert_all(sample_translations_large)

        report = reinserter.get_report()
        assert report["statistics"]["successful"] == 5000
        assert t["elapsed"] < 30, f"Batch injection took {t['elapsed']:.2f}s (limit 30s)"


class TestIndividualInjection:
    """Measure per-entry injection time."""

    def test_individual_injection_time(self, rom_32mb, large_texts, timer):
        rom = bytearray(rom_32mb)
        reinserter = SmartReinserter(rom)

        for entry in large_texts:
            start = time.perf_counter()
            success = reinserter.reinsert_text(entry)
            elapsed = time.perf_counter() - start

            assert success, f"Injection failed at offset {entry['offset']:#x}"
            assert elapsed < 0.1, (
                f"Single injection at {entry['offset']:#x} took {elapsed:.4f}s (limit 100ms)"
            )

    def test_small_text_injection(self, rom_32mb, timer):
        rom = bytearray(rom_32mb)
        reinserter = SmartReinserter(rom)

        entry = {
            "offset": 0x200000,
            "translation": "Hi",
            "encoding": "pokemon",
            "original_length": 10,
            "max_length": 12,
        }

        with timer("small text injection") as t:
            for _ in range(1000):
                reinserter.reinsert_text(entry)

        assert t["elapsed"] < 5, f"1000 small injections took {t['elapsed']:.2f}s"


class TestRelocationVsInPlace:
    """Compare relocation and in-place injection speed."""

    def test_inplace_injection(self, rom_32mb, sample_translations_small, timer):
        rom = bytearray(rom_32mb)
        reinserter = SmartReinserter(rom, allow_relocate=False)

        with timer("in-place 50 entries") as t:
            reinserter.reinsert_all(sample_translations_small)

        assert reinserter.stats["success"] == 50
        assert t["elapsed"] < 5

    def test_relocation_injection(self, rom_32mb, timer):
        rom = bytearray(rom_32mb)
        # Plant some occupied data so the allocator has real blocks to scan
        for i in range(0, 4096, 2):
            rom[0x100 + i] = 0xAB
        reinserter = SmartReinserter(rom, allow_relocate=True)

        translations = []
        for i in range(50):
            translations.append(
                {
                    "offset": 0x100 + i * 2,
                    "translation": "Relocated text that overflows its slot easily",
                    "encoding": "pokemon",
                    "original_length": 1,
                    "max_length": 2,
                    "pointer_offsets": [0x50 + i * 4],
                }
            )

        with timer("relocation 50 entries") as t:
            reinserter.reinsert_all(translations)

        assert reinserter.stats["relocated"] > 0
        assert t["elapsed"] < 5


class TestEncodingPerformance:
    """Measure raw encoding speed independent of ROM writes."""

    def test_pokemon_encoding_throughput(self, timer):
        text = "This is a moderately long text for encoding benchmark testing purposes"

        with timer("encode 10000 pokemon strings") as t:
            for _ in range(10000):
                TextEncoder.encode_pokemon(text)

        assert t["elapsed"] < 5, f"10k encodes took {t['elapsed']:.2f}s"

    def test_ascii_encoding_throughput(self, timer):
        text = "Simple ASCII text for benchmark"

        with timer("encode 10000 ascii strings") as t:
            for _ in range(10000):
                TextEncoder.encode_ascii(text)

        assert t["elapsed"] < 5, f"10k encodes took {t['elapsed']:.2f}s"
