"""Edge-whitespace preservation when loading translations from CSV.

Credits/staff-roll strings centre themselves with leading and trailing
blank lines ('\n\n Skeli\n Criminon\n\n'); battle prefixes keep a
trailing space ("L'adversaire "). A blanket strip() destroys those
layouts, so load_from_csv must mirror the edges of the English source.
"""

import csv
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core.text_converter import CSVToJSONConverter

FIELDNAMES = [
    'offset', 'original_text', 'spanish_text', 'original_length',
    'padding_available', 'real_max_length', 'encoding', 'category',
    'translation', 'notes',
]


def _load(rows):
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / 'translations.csv'
        with path.open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        converter = CSVToJSONConverter()
        converter.allow_too_long = True
        converter.load_from_csv(path)
        return {entry.offset: entry.translation for entry in converter.entries}


def _row(offset, original, translation):
    return {
        'offset': hex(offset),
        'original_text': original,
        'spanish_text': '',
        'original_length': str(len(original)),
        'padding_available': '0',
        'real_max_length': str(len(original)),
        'encoding': 'pokemon',
        'category': 'description',
        'translation': translation,
        'notes': '',
    }


class CsvEdgeWhitespaceTests(unittest.TestCase):
    def test_credits_blank_lines_survive(self):
        text = '\n\n Skeli\n Lich-Lord-F\n Criminon\n\n'
        result = _load([_row(0x1EEFE8C, text, text)])
        self.assertEqual(result[0x1EEFE8C], text)

    def test_prefix_trailing_space_survives(self):
        result = _load([_row(0x10, 'The opposing ', "L'adversaire ")])
        self.assertEqual(result[0x10], "L'adversaire ")

    def test_plain_text_still_stripped(self):
        result = _load([_row(0x20, 'Hello!', '  Salut !  \n')])
        self.assertEqual(result[0x20], 'Salut !')


if __name__ == '__main__':
    unittest.main()
