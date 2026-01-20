#!/usr/bin/env python3
"""
28 - Export Trilingual Translation CSV

Builds a CSV with English/Spanish/French columns for translation work.
The output stays compatible with 09_csv_to_json_v2.py (translation column).

Defaults:
- English base: latest output/differences/*_diff_with_padding.json
- Spanish texts: output/extracted/extracted_texts/spanishrom_texts.json
- French texts: optional, auto-detected in output/translation/
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.text_converter import JSONToCSVConverter


CSV_FIELDNAMES = [
    'offset',
    'original_text',
    'spanish_text',
    'original_length',
    'padding_available',
    'real_max_length',
    'encoding',
    'category',
    'translation',
    'notes'
]


def _parse_offset(value: object) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.lower().startswith('0x'):
            try:
                return int(text, 16)
            except ValueError:
                return None
        try:
            return int(text)
        except ValueError:
            return None
    return None


def _find_latest(path: Path, pattern: str) -> Optional[Path]:
    if not path.exists():
        return None
    candidates = list(path.glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _resolve_english_base(explicit: Optional[Path]) -> Optional[Path]:
    if explicit:
        return explicit
    diff_dir = Path('output/differences')
    latest = _find_latest(diff_dir, '*_diff_with_padding.json')
    if latest:
        return latest
    fallback = diff_dir / 'englishrom_diff_only.json'
    if fallback.exists():
        return fallback
    return None


def _resolve_french(explicit: Optional[Path]) -> Optional[Path]:
    if explicit:
        return explicit
    translation_dir = Path('output/translation')
    latest_ready = _find_latest(translation_dir, '*_translation_ready.json')
    if latest_ready:
        return latest_ready
    fallback = translation_dir / 'french_texts.json'
    if fallback.exists():
        return fallback
    return None


def _load_json(path: Path) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _load_english_entries(path: Path) -> List[dict]:
    data = _load_json(path)
    texts = data.get('texts')
    if texts is None:
        raise ValueError(f"English base JSON missing 'texts' list: {path}")

    entries: List[dict] = []
    for item in texts:
        offset = _parse_offset(item.get('offset'))
        if offset is None:
            continue
        text = item.get('text', '')
        length = item.get('length')
        if length is None:
            length = len(text)
        padding = item.get('padding_available', 0) or 0
        real_max = item.get('real_max_length')
        if real_max is None:
            real_max = length + padding
        entry = {
            'offset': offset,
            'text': text,
            'length': length,
            'padding_available': padding,
            'real_max_length': real_max,
            'encoding': item.get('encoding', 'pokemon'),
            'category': item.get('category')
        }
        entries.append(entry)

    entries.sort(key=lambda e: e['offset'])
    return entries


def _load_spanish_map(path: Path) -> Dict[int, str]:
    if not path.exists():
        return {}
    data = _load_json(path)
    texts = data.get('texts', [])
    mapping: Dict[int, str] = {}
    for item in texts:
        offset = _parse_offset(item.get('offset'))
        if offset is None:
            continue
        text = item.get('decoded_text') or item.get('text') or ''
        mapping[offset] = text
    return mapping


def _load_french_map(path: Optional[Path]) -> Dict[int, str]:
    if path is None or not path.exists():
        return {}
    data = _load_json(path)

    if isinstance(data, dict) and 'translations' in data:
        items = data.get('translations', [])
    elif isinstance(data, dict) and 'texts' in data:
        items = data.get('texts', [])
    elif isinstance(data, dict):
        mapping = {}
        for key, value in data.items():
            offset = _parse_offset(key)
            if offset is None:
                continue
            mapping[offset] = value if isinstance(value, str) else str(value)
        return mapping
    else:
        return {}

    mapping: Dict[int, str] = {}
    for item in items:
        offset = _parse_offset(item.get('offset'))
        if offset is None:
            continue
        text = item.get('french') or item.get('text') or item.get('translation') or ''
        mapping[offset] = text
    return mapping


def _write_csv(rows: List[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Export a trilingual translation CSV (EN/ES/FR).'
    )
    parser.add_argument('--english', type=Path, help='English diff-with-padding JSON')
    parser.add_argument(
        '--spanish',
        type=Path,
        default=Path('output/extracted/extracted_texts/spanishrom_texts.json'),
        help='Spanish extracted JSON'
    )
    parser.add_argument('--french', type=Path, help='Optional French translation JSON')
    parser.add_argument('--output', type=Path, help='Output CSV path')

    args = parser.parse_args()

    english_path = _resolve_english_base(args.english)
    if not english_path or not english_path.exists():
        print('Error: English base JSON not found.')
        return 1

    french_path = _resolve_french(args.french)
    output_path = args.output
    if output_path is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
        output_path = Path('output/translation') / f'{date_str}_trilingual_translation.csv'

    english_entries = _load_english_entries(english_path)
    spanish_map = _load_spanish_map(args.spanish)
    french_map = _load_french_map(french_path)

    converter = JSONToCSVConverter()
    rows: List[dict] = []
    spanish_hits = 0
    french_hits = 0

    for entry in english_entries:
        offset = entry['offset']
        english_text = entry['text']
        spanish_text = spanish_map.get(offset, '')
        french_text = french_map.get(offset, '')

        if spanish_text:
            spanish_hits += 1
        if french_text:
            french_hits += 1

        category = entry.get('category') or converter.categorize_text(english_text, offset)

        rows.append({
            'offset': f'0x{offset:08X}',
            'original_text': english_text,
            'spanish_text': spanish_text,
            'original_length': entry['length'],
            'padding_available': entry['padding_available'],
            'real_max_length': entry['real_max_length'],
            'encoding': entry['encoding'],
            'category': category,
            'translation': french_text,
            'notes': ''
        })

    _write_csv(rows, output_path)

    print(f'English base: {english_path}')
    if args.spanish.exists():
        print(f'Spanish map: {args.spanish}')
    else:
        print('Spanish map: missing (column left blank)')
    if french_path:
        print(f'French map: {french_path}')
    else:
        print('French map: not provided (translation column empty)')
    print(f'Rows: {len(rows)} (ES filled: {spanish_hits}, FR filled: {french_hits})')
    print(f'CSV written: {output_path}')
    print('Next: edit the "translation" column and run 09_csv_to_json_v2.py')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
