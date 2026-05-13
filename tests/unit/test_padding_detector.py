import unittest
from unittest.mock import MagicMock

from src.core.padding_detector import PaddingDetector


def _make_mock_rom(data: bytes) -> MagicMock:
    """Create a mock ROMReader with the given data."""
    mock = MagicMock()
    mock.rom_data = bytearray(data)
    mock.rom_size = len(data)
    return mock


class TestDetectPadding(unittest.TestCase):

    def test_consecutive_zero_padding(self):
        data = b"HELLO" + b"\x00" * 10 + b"NEXT"
        rom = _make_mock_rom(data)
        detector = PaddingDetector(rom)
        padding = detector.detect_padding(0, 5)
        self.assertEqual(padding, 10)

    def test_consecutive_ff_padding(self):
        data = b"HI" + b"\xFF" * 5 + b"X"
        rom = _make_mock_rom(data)
        detector = PaddingDetector(rom)
        padding = detector.detect_padding(0, 2)
        self.assertEqual(padding, 5)

    def test_no_padding(self):
        data = b"HELLOWORLD"
        rom = _make_mock_rom(data)
        detector = PaddingDetector(rom)
        padding = detector.detect_padding(0, 5)
        self.assertEqual(padding, 0)

    def test_mixed_padding(self):
        data = b"AB" + b"\x00\xFF\x00" + b"CD"
        rom = _make_mock_rom(data)
        detector = PaddingDetector(rom)
        padding = detector.detect_padding(0, 2)
        self.assertEqual(padding, 3)

    def test_padding_at_end_of_rom(self):
        data = b"TEST" + b"\x00" * 3
        rom = _make_mock_rom(data)
        detector = PaddingDetector(rom)
        padding = detector.detect_padding(0, 4)
        self.assertEqual(padding, 3)

    def test_extended_search(self):
        data = b"AB" + b"\x01" + b"\x00" * 5 + b"CD"
        rom = _make_mock_rom(data)
        detector = PaddingDetector(rom)
        padding = detector.detect_padding(0, 2, extended_search=True)
        self.assertEqual(padding, 5)


class TestAnalyzeText(unittest.TestCase):

    def test_analyze_enriches_entry(self):
        data = b"HELLO" + b"\x00" * 7 + b"NEXT"
        rom = _make_mock_rom(data)
        detector = PaddingDetector(rom)
        entry = {"offset": 0, "length": 5, "text": "HELLO"}
        enriched = detector.analyze_text(entry)
        self.assertEqual(enriched["padding_available"], 7)
        self.assertEqual(enriched["real_max_length"], 12)
        self.assertEqual(enriched["text"], "HELLO")

    def test_analyze_does_not_mutate_original(self):
        data = b"AB" + b"\x00" * 3
        rom = _make_mock_rom(data)
        detector = PaddingDetector(rom)
        original = {"offset": 0, "length": 2}
        enriched = detector.analyze_text(original)
        self.assertNotIn("padding_available", original)
        self.assertIn("padding_available", enriched)


class TestAnalyzeAllTexts(unittest.TestCase):

    def test_analyze_multiple(self):
        data = b"AB" + b"\x00" * 3 + b"CD" + b"\x00" * 5 + b"END"
        rom = _make_mock_rom(data)
        detector = PaddingDetector(rom)
        texts = [
            {"offset": 0, "length": 2},
            {"offset": 5, "length": 2},
        ]
        results = detector.analyze_all_texts(texts)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["padding_available"], 3)
        self.assertEqual(results[1]["padding_available"], 5)


class TestStatistics(unittest.TestCase):

    def test_stats_updated_correctly(self):
        data = b"A" + b"\x00" * 5 + b"B" + b"\x00" * 0 + b"C"
        rom = _make_mock_rom(data)
        detector = PaddingDetector(rom)
        detector.analyze_text({"offset": 0, "length": 1})
        detector.analyze_text({"offset": 6, "length": 1})
        self.assertEqual(detector.stats["total_analyzed"], 2)
        self.assertEqual(detector.stats["with_padding"], 1)
        self.assertEqual(detector.stats["without_padding"], 1)
        self.assertEqual(detector.stats["max_padding"], 5)

    def test_generate_report_empty(self):
        rom = _make_mock_rom(b"\x00" * 10)
        detector = PaddingDetector(rom)
        report = detector.generate_report()
        self.assertEqual(report["message"], "No texts analyzed")

    def test_generate_report_with_data(self):
        data = b"A" + b"\x00" * 5 + b"END"
        rom = _make_mock_rom(data)
        detector = PaddingDetector(rom)
        detector.analyze_text({"offset": 0, "length": 1})
        detector.stats["avg_padding"] = 5.0
        report = detector.generate_report()
        self.assertIn("statistics", report)
        self.assertIn("recommendations", report)

    def test_repr(self):
        rom = _make_mock_rom(b"\x00" * 10)
        detector = PaddingDetector(rom)
        self.assertIn("no analysis yet", repr(detector))


if __name__ == "__main__":
    unittest.main()
