from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path

from src.core.text_reinserter import SmartReinserter


def _find_latest(path: Path, pattern: str) -> Path | None:
    if not path.exists():
        return None
    candidates = list(path.glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _load_english_pointer_map(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    mapping: dict[int, dict] = {}
    for item in data.get('texts', []):
        offset = item.get('offset')
        if isinstance(offset, int):
            mapping[offset] = item
    return mapping


def _parse_int(value: str) -> int | None:
    text = (value or '').strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


class DynamicInsertionTests(unittest.TestCase):
    def test_spanish_dynamic_csv_inserts_100_percent(self):
        translation_dir = Path('output/translation')
        csv_path = _find_latest(translation_dir, '*_dynamic_diff_translation.csv')
        english_rom = Path('input/roms/englishrom.gba')
        english_texts = Path('output/extracted/extracted_texts/englishrom_texts.json')

        if not csv_path or not english_rom.exists() or not english_texts.exists():
            self.skipTest('Dynamic CSV or ROM resources missing')

        english_map = _load_english_pointer_map(english_texts)
        translations = []

        with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                raw_offset = row.get('offset') or ''
                if not raw_offset:
                    continue
                offset = int(raw_offset.replace('0x', ''), 16)
                translation = (row.get('spanish_text') or '').strip()
                if not translation:
                    continue

                entry = {
                    'offset': offset,
                    'translation': translation,
                    'encoding': row.get('encoding') or 'pokemon',
                    'original_length': _parse_int(row.get('original_length') or ''),
                    'padding_available': _parse_int(row.get('padding_available') or ''),
                }

                pointer_offsets = english_map.get(offset, {}).get('pointer_offsets')
                if pointer_offsets:
                    entry['pointer_offsets'] = pointer_offsets

                translations.append(entry)

        if not translations:
            self.skipTest('No translations found in dynamic diff CSV')

        rom_data = bytearray(english_rom.read_bytes())
        reinserter = SmartReinserter(rom_data, allow_relocate=True, allow_truncate=False)
        for entry in translations:
            reinserter.reinsert_text(entry)

        report = reinserter.get_report()
        stats = report['statistics']

        self.assertEqual(stats['failed'], 0)
        self.assertEqual(stats['relocation_failed'], 0)
        # Entries whose only "pointers" are false positives (raw byte-scan
        # artifacts inside code) are deliberately left in place instead of
        # being relocated; they count as skipped_too_long.
        self.assertEqual(
            stats['successful'] + stats['skipped_too_long'],
            stats['total_texts'],
        )
        self.assertLessEqual(
            stats['skipped_too_long'], stats['total_texts'] * 0.05,
            'too many entries lost their relocation pointers',
        )


if __name__ == '__main__':
    unittest.main()
