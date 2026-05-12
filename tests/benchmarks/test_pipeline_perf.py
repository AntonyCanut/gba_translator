"""Benchmark tests for full pipeline performance."""

import json
import os
import tempfile

import pytest

from src.core.text_reinserter import SmartReinserter, FreeSpaceAllocator
from src.core.text_codec import TextEncoder, TextDecoder

pytestmark = pytest.mark.benchmark

TRANSLATION_JSON_ENV = "GBA_TEST_TRANSLATIONS_JSON"


class TestFullPipeline:
    """Measure the complete load-inject-validate cycle."""

    def test_pipeline_in_memory(self, rom_32mb, sample_translations_large, timer):
        """Full in-memory pipeline: encode + inject + report."""
        rom = bytearray(rom_32mb)
        reinserter = SmartReinserter(rom, allow_relocate=True)

        with timer("full pipeline 5000 entries") as t:
            reinserter.reinsert_all(sample_translations_large)
            report = reinserter.get_report()

        assert report["statistics"]["successful"] == 5000
        assert t["elapsed"] < 30, f"Pipeline took {t['elapsed']:.2f}s (limit 30s)"

    def test_pipeline_with_relocation(self, rom_with_data, timer):
        """Pipeline with mixed in-place and relocation."""
        rom = bytearray(rom_with_data)
        reinserter = SmartReinserter(rom, allow_relocate=True)

        translations = []
        for i in range(200):
            translations.append(
                {
                    "offset": 0x100000 + i * 64,
                    "translation": f"Texte traduit numero {i} avec du contenu supplementaire",
                    "encoding": "pokemon",
                    "original_length": 40,
                    "max_length": 60,
                    "pointer_offsets": [0x50 + i * 4],
                }
            )

        with timer("pipeline 200 entries with relocation") as t:
            reinserter.reinsert_all(translations)
            report = reinserter.get_report()

        assert t["elapsed"] < 10


class TestIPSPatchGeneration:
    """Measure IPS patch creation speed."""

    def test_ips_patch_creation(self, rom_32mb, timer):
        """Measure time to diff and produce an IPS-like patch."""
        original = bytes(rom_32mb)
        modified = bytearray(rom_32mb)

        reinserter = SmartReinserter(modified)
        for i in range(1000):
            reinserter.reinsert_text(
                {
                    "offset": 0x100000 + i * 64,
                    "translation": f"Patch text {i}",
                    "encoding": "pokemon",
                    "original_length": 40,
                    "max_length": 60,
                }
            )

        with timer("IPS diff 1000 changes on 32MB") as t:
            records = []
            i = 0
            n = len(original)
            while i < n:
                if modified[i] != original[i]:
                    start = i
                    while i < n and modified[i] != original[i]:
                        i += 1
                    records.append((start, bytes(modified[start:i])))
                else:
                    i += 1

        print(f"  [IPS] {len(records)} change records")
        assert t["elapsed"] < 30, f"IPS diff took {t['elapsed']:.2f}s"


class TestTranslationLoading:
    """Measure JSON translation file loading and parsing speed."""

    def test_load_generated_json(self, timer):
        """Generate a temporary JSON translation file and measure load time."""
        entries = []
        for i in range(5000):
            entries.append(
                {
                    "offset": f"0x{0x100000 + i * 64:08X}",
                    "text": f"Original text {i}",
                    "translation": f"Texte traduit {i}",
                    "encoding": "pokemon",
                    "original_length": 30,
                }
            )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(entries, f)
            tmp_path = f.name

        try:
            with timer("load 5000-entry JSON") as t:
                with open(tmp_path, "r") as f:
                    loaded = json.load(f)
        finally:
            os.unlink(tmp_path)

        assert len(loaded) == 5000
        assert t["elapsed"] < 5, f"JSON load took {t['elapsed']:.2f}s"

    def test_parse_offsets(self, timer):
        """Measure offset parsing throughput."""
        hex_offsets = [f"0x{0x100000 + i * 64:08X}" for i in range(10000)]

        with timer("parse 10000 hex offsets") as t:
            parsed = [int(h, 16) for h in hex_offsets]

        assert len(parsed) == 10000
        assert t["elapsed"] < 1


class TestEncodeDecode:
    """Measure codec round-trip performance."""

    def test_encode_decode_roundtrip(self, timer):
        texts = [f"Sample text for round-trip {i}" for i in range(1000)]

        with timer("1000 encode-decode roundtrips") as t:
            for text in texts:
                encoded = TextEncoder.encode_pokemon(text)
                decoded = TextDecoder.decode_pokemon(encoded)

        assert t["elapsed"] < 5

    def test_encode_with_special_chars(self, timer):
        texts_fr = [
            "Les Pokemon sont tres forts",
            "Prends soin de toi",
            "Combat termine",
        ] * 1000

        with timer("3000 french text encodes") as t:
            for text in texts_fr:
                TextEncoder.encode_pokemon(text)

        assert t["elapsed"] < 5
