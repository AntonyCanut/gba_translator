#!/usr/bin/env python3
"""
Export dynamic (variable-driven) texts to a trilingual CSV.

Filters English extracted texts by dynamic token patterns (e.g. <0xFD>, <0xF7>),
then attaches Spanish equivalents and existing French translations.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.padding_detector import PaddingDetector
from src.core.rom_reader import ROMReader
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
    'notes',
]

DYNAMIC_TOKEN_RE = re.compile(r'<0xFD>|<0xF7>')

BATTLE_KEYWORDS = (
    ' used ',
    ' sent out ',
    ' fainted',
    ' foe ',
    ' enemy ',
    ' wild ',
    ' battled ',
    ' battle ',
    ' hit ',
    ' critical',
    ' growled',
    ' appeared',
    ' appeared!',
    ' ran away',
)


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


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _load_spanish_map(path: Path) -> Dict[int, str]:
    if not path.exists():
        return {}
    data = _load_json(path)
    mapping: Dict[int, str] = {}
    for item in data.get('texts', []):
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


def _is_dynamic(text: str) -> bool:
    return bool(DYNAMIC_TOKEN_RE.search(text))


def _is_battle(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in BATTLE_KEYWORDS)


def _length_without_terminator(entry: dict) -> int:
    byte_length = entry.get('byte_length') or entry.get('length')
    if byte_length is None:
        return max(len(entry.get('text', '')), 0)
    try:
        return max(int(byte_length) - 1, 0)
    except (TypeError, ValueError):
        return max(len(entry.get('text', '')), 0)


def _write_csv(rows: List[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Export dynamic/battle texts to a trilingual CSV.'
    )
    parser.add_argument(
        '--english',
        type=Path,
        default=Path('output/extracted/extracted_texts/englishrom_texts.json'),
        help='English extracted JSON',
    )
    parser.add_argument(
        '--spanish',
        type=Path,
        default=Path('output/extracted/extracted_texts/spanishrom_texts.json'),
        help='Spanish extracted JSON',
    )
    parser.add_argument(
        '--french',
        type=Path,
        help='Optional French translation JSON',
    )
    parser.add_argument(
        '--rom',
        type=Path,
        default=Path('input/roms/englishrom.gba'),
        help='English ROM for padding detection',
    )
    parser.add_argument('--battle-only', action='store_true', help='Filter battle-like texts')
    parser.add_argument(
        '--include-same',
        action='store_true',
        help='Include entries where Spanish is missing or identical to English',
    )
    parser.add_argument('--output', type=Path, help='Output CSV path')

    args = parser.parse_args()

    if not args.english.exists():
        print(f'Error: English extracted JSON not found: {args.english}')
        return 1
    if not args.rom.exists():
        print(f'Error: English ROM not found: {args.rom}')
        return 1

    if args.french is None:
        translation_dir = Path('output/translation')
        args.french = _find_latest(translation_dir, '*_translation_ready.json')

    output_path = args.output
    if output_path is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
        if args.include_same:
            suffix = 'battle_dynamic' if args.battle_only else 'dynamic'
        else:
            suffix = 'battle_dynamic_diff' if args.battle_only else 'dynamic_diff'
        output_path = Path('output/translation') / f'{date_str}_{suffix}_translation.csv'

    english_data = _load_json(args.english)
    spanish_map = _load_spanish_map(args.spanish)
    french_map = _load_french_map(args.french)

    rom_reader = ROMReader(str(args.rom))
    rom_reader.load()
    detector = PaddingDetector(rom_reader)
    converter = JSONToCSVConverter()

    rows: List[dict] = []
    spanish_hits = 0
    french_hits = 0

    for item in english_data.get('texts', []):
        offset = _parse_offset(item.get('offset'))
        if offset is None:
            continue
        text = item.get('decoded_text') or item.get('text') or ''
        if not text:
            continue
        if not _is_dynamic(text):
            continue
        if args.battle_only and not _is_battle(text):
            continue

        length = _length_without_terminator(item)
        padding = detector.detect_padding(offset, length, extended_search=True)
        real_max = length + padding

        spanish_text = spanish_map.get(offset, '')
        if not args.include_same and (not spanish_text or spanish_text == text):
            continue
        french_text = french_map.get(offset, '')
        if spanish_text:
            spanish_hits += 1
        if french_text:
            french_hits += 1

        category = 'battle' if args.battle_only else converter.categorize_text(text, offset)

        rows.append({
            'offset': f'0x{offset:08X}',
            'original_text': text,
            'spanish_text': spanish_text,
            'original_length': length,
            'padding_available': padding,
            'real_max_length': real_max,
            'encoding': item.get('encoding', 'pokemon'),
            'category': category,
            'translation': french_text,
            'notes': '',
        })

    _write_csv(rows, output_path)

    print(f'English base: {args.english}')
    print(f'Spanish map: {args.spanish if args.spanish.exists() else "missing"}')
    print(f'French map: {args.french if args.french else "not provided"}')
    print(f'Rows: {len(rows)} (ES filled: {spanish_hits}, FR filled: {french_hits})')
    print(f'CSV written: {output_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
