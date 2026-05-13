import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.core.text_converter import TextEntry, JSONToCSVConverter, CSVToJSONConverter


class TestTextEntry(unittest.TestCase):

    def test_from_dict(self):
        data = {
            "offset": 0x1000,
            "text": "Hello",
            "length": 5,
            "encoding": "pokemon",
            "padding_available": 3,
            "category": "dialogue",
        }
        entry = TextEntry.from_dict(data)
        self.assertEqual(entry.offset, 0x1000)
        self.assertEqual(entry.text, "Hello")
        self.assertEqual(entry.real_max_length, 8)
        self.assertEqual(entry.category, "dialogue")

    def test_to_dict_roundtrip(self):
        entry = TextEntry(offset=0x200, text="Test", length=4, encoding="ascii")
        d = entry.to_dict()
        restored = TextEntry.from_dict(d)
        self.assertEqual(restored.offset, entry.offset)
        self.assertEqual(restored.text, entry.text)
        self.assertEqual(restored.length, entry.length)

    def test_to_csv_row(self):
        entry = TextEntry(offset=0xFF, text="Hi", length=2, encoding="pokemon")
        row = entry.to_csv_row()
        self.assertEqual(row["offset"], "0x000000FF")
        self.assertEqual(row["original_text"], "Hi")
        self.assertEqual(row["encoding"], "pokemon")

    def test_real_max_length(self):
        entry = TextEntry(offset=0, text="A", length=1, encoding="ascii", padding_available=10)
        self.assertEqual(entry.real_max_length, 11)

    def test_validate_translation_missing(self):
        entry = TextEntry(offset=0, text="A", length=1, encoding="ascii")
        is_valid, msg = entry.validate_translation()
        self.assertFalse(is_valid)
        self.assertIn("manquante", msg)

    def test_repr(self):
        entry = TextEntry(offset=0x100, text="Short text", length=10, encoding="pokemon")
        self.assertIn("0x00000100", repr(entry))


class TestJSONToCSVConverter(unittest.TestCase):

    def _make_json(self, texts):
        return {
            "rom_name": "test.gba",
            "rom_size": 16 * 1024 * 1024,
            "analysis_date": "2024-01-01",
            "text_count": len(texts),
            "texts": texts,
        }

    def test_load_and_export(self):
        texts = [
            {"offset": 0x100, "text": "Hello!", "length": 6, "encoding": "pokemon"},
            {"offset": 0x200, "text": "World", "length": 5, "encoding": "ascii"},
        ]
        json_data = self._make_json(texts)

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(json_data, f)
            json_path = Path(f.name)

        converter = JSONToCSVConverter()
        converter.load_from_json(json_path)
        self.assertEqual(len(converter.entries), 2)
        self.assertEqual(converter.metadata["rom_name"], "test.gba")

        csv_path = Path(tempfile.mktemp(suffix=".csv"))
        converter.save_to_csv(csv_path)
        self.assertTrue(csv_path.exists())

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["original_text"], "Hello!")
        json_path.unlink(missing_ok=True)
        csv_path.unlink(missing_ok=True)

    def test_categorize_text(self):
        conv = JSONToCSVConverter()
        self.assertEqual(conv.categorize_text("Are you ready?", 0), "dialogue")
        self.assertEqual(conv.categorize_text("Pallet Town", 0), "location")
        self.assertEqual(conv.categorize_text("saved the game to menu", 0), "system")
        self.assertEqual(conv.categorize_text("A" * 50, 0), "description")
        self.assertEqual(conv.categorize_text("X", 0), "other")

    def test_get_statistics(self):
        conv = JSONToCSVConverter()
        conv.entries = [
            TextEntry(0, "Hi!", 3, "pokemon", category="dialogue"),
            TextEntry(1, "Bye", 3, "pokemon", category="dialogue"),
            TextEntry(2, "Menu", 4, "pokemon", category="system"),
        ]
        stats = conv.get_statistics()
        self.assertEqual(stats["total_texts"], 3)
        self.assertEqual(stats["categories"]["dialogue"], 2)
        self.assertEqual(stats["categories"]["system"], 1)


class TestCSVToJSONConverter(unittest.TestCase):

    def _make_csv(self, rows):
        path = Path(tempfile.mktemp(suffix=".csv"))
        fieldnames = [
            "offset", "original_text", "original_length",
            "padding_available", "real_max_length", "encoding",
            "category", "translation", "notes",
        ]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        return path

    def test_load_valid_csv(self):
        rows = [
            {
                "offset": "0x00000100",
                "original_text": "Hello",
                "original_length": "5",
                "padding_available": "5",
                "real_max_length": "10",
                "encoding": "ascii",
                "category": "dialogue",
                "translation": "Bonjour",
                "notes": "",
            },
        ]
        csv_path = self._make_csv(rows)
        conv = CSVToJSONConverter()
        conv.load_from_csv(csv_path)
        self.assertEqual(len(conv.entries), 1)
        self.assertEqual(conv.entries[0].translation, "Bonjour")
        self.assertFalse(conv.has_errors())
        csv_path.unlink(missing_ok=True)

    def test_missing_translation_warning(self):
        rows = [
            {
                "offset": "0x00000100",
                "original_text": "Hello",
                "original_length": "5",
                "padding_available": "5",
                "real_max_length": "10",
                "encoding": "ascii",
                "category": "dialogue",
                "translation": "",
                "notes": "",
            },
        ]
        csv_path = self._make_csv(rows)
        conv = CSVToJSONConverter()
        conv.load_from_csv(csv_path)
        self.assertEqual(len(conv.entries), 0)
        self.assertEqual(len(conv.warnings), 1)
        csv_path.unlink(missing_ok=True)

    def test_save_to_json(self):
        conv = CSVToJSONConverter()
        conv.entries = [
            TextEntry(0x100, "Hello", 5, "ascii", padding_available=5, translation="Bonjour"),
        ]
        json_path = Path(tempfile.mktemp(suffix=".json"))
        conv.save_to_json(json_path, "test.csv")
        with open(json_path, "r") as f:
            data = json.load(f)
        self.assertEqual(data["total_translations"], 1)
        self.assertEqual(data["source_csv"], "test.csv")
        json_path.unlink(missing_ok=True)

    def test_get_statistics(self):
        conv = CSVToJSONConverter()
        conv.entries = [TextEntry(0, "A", 1, "ascii", translation="B")]
        conv.errors = [{"row": 2, "error": "too long"}]
        conv.warnings = [{"row": 3, "message": "missing"}]
        stats = conv.get_statistics()
        self.assertEqual(stats["successful"], 1)
        self.assertEqual(len(stats["errors"]), 1)
        self.assertEqual(len(stats["warnings"]), 1)


if __name__ == "__main__":
    unittest.main()
