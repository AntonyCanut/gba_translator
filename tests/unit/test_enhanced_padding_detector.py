import unittest
from unittest.mock import MagicMock

from src.core.enhanced_padding_detector import EnhancedPaddingDetector


def _make_mock_rom(data: bytes) -> MagicMock:
    mock = MagicMock()
    mock.rom_data = bytearray(data)
    mock.rom_size = len(data)
    return mock


class TestDetectExtendedPadding(unittest.TestCase):

    def test_continuous_padding(self):
        data = b"TEXT" + b"\x00" * 20
        rom = _make_mock_rom(data)
        detector = EnhancedPaddingDetector(rom)
        total, details = detector.detect_extended_padding(0, 4)
        self.assertEqual(total, 20)
        self.assertEqual(details["confidence"], "high")
        self.assertEqual(details["gaps_found"], 0)

    def test_padding_with_small_gaps(self):
        data = b"AB" + b"\x00" * 5 + b"\x01" + b"\x00" * 5 + b"END"
        rom = _make_mock_rom(data)
        detector = EnhancedPaddingDetector(rom)
        total, details = detector.detect_extended_padding(0, 2, max_gap=3)
        self.assertEqual(total, 10)
        self.assertIn(details["confidence"], ("medium", "low"))
        self.assertGreater(details["gaps_found"], 0)

    def test_stops_after_max_gap(self):
        data = b"AB" + b"\x00" * 3 + b"\x01\x02\x03\x04\x05\x06" + b"\x00" * 10
        rom = _make_mock_rom(data)
        detector = EnhancedPaddingDetector(rom)
        total, details = detector.detect_extended_padding(0, 2, max_gap=5)
        self.assertEqual(total, 3)

    def test_no_padding(self):
        data = b"ABCDEFGHIJ"
        rom = _make_mock_rom(data)
        detector = EnhancedPaddingDetector(rom)
        total, details = detector.detect_extended_padding(0, 2, max_search=8)
        self.assertEqual(total, 0)


class TestCalculateConfidence(unittest.TestCase):

    def test_high_confidence(self):
        rom = _make_mock_rom(b"\x00" * 10)
        detector = EnhancedPaddingDetector(rom)
        self.assertEqual(detector._calculate_confidence(5, 0, [{"start": 0, "length": 5}]), "high")

    def test_medium_confidence(self):
        rom = _make_mock_rom(b"\x00" * 10)
        detector = EnhancedPaddingDetector(rom)
        self.assertEqual(
            detector._calculate_confidence(5, 2, [{"start": 0, "length": 3}, {"start": 4, "length": 2}]),
            "medium",
        )

    def test_low_confidence(self):
        rom = _make_mock_rom(b"\x00" * 10)
        detector = EnhancedPaddingDetector(rom)
        seqs = [{"start": i, "length": 1} for i in range(5)]
        self.assertEqual(detector._calculate_confidence(5, 4, seqs), "low")


class TestDetectWithValidation(unittest.TestCase):

    def test_standard_mode(self):
        data = b"AB" + b"\x00" * 5 + b"CD"
        rom = _make_mock_rom(data)
        detector = EnhancedPaddingDetector(rom, aggressive_mode=False)
        std, ext, details = detector.detect_with_validation(0, 2)
        self.assertEqual(std, 5)
        self.assertEqual(ext, 5)
        self.assertEqual(details["confidence"], "high")

    def test_aggressive_mode(self):
        data = b"AB" + b"\x00" * 5 + b"\x01" + b"\x00" * 5 + b"END"
        rom = _make_mock_rom(data)
        detector = EnhancedPaddingDetector(rom, aggressive_mode=True)
        std, ext, details = detector.detect_with_validation(0, 2)
        self.assertEqual(std, 5)
        self.assertGreaterEqual(ext, std)


class TestAnalyzeTextEnhanced(unittest.TestCase):

    def test_enriches_entry(self):
        data = b"HELLO" + b"\x00" * 10 + b"NEXT"
        rom = _make_mock_rom(data)
        detector = EnhancedPaddingDetector(rom, aggressive_mode=True)
        entry = {"offset": 0, "length": 5, "text": "HELLO"}
        enriched = detector.analyze_text_enhanced(entry)
        self.assertIn("padding_available", enriched)
        self.assertIn("padding_extended", enriched)
        self.assertIn("padding_confidence", enriched)
        self.assertEqual(enriched["real_max_length"], 5 + enriched["padding_available"])


class TestRepr(unittest.TestCase):

    def test_repr_no_analysis(self):
        rom = _make_mock_rom(b"\x00" * 10)
        detector = EnhancedPaddingDetector(rom)
        self.assertIn("no analysis yet", repr(detector))
        self.assertIn("standard", repr(detector))

    def test_repr_aggressive(self):
        rom = _make_mock_rom(b"\x00" * 10)
        detector = EnhancedPaddingDetector(rom, aggressive_mode=True)
        self.assertIn("aggressive", repr(detector))


if __name__ == "__main__":
    unittest.main()
