#!/usr/bin/env python3
"""
Apply translations from a dynamic diff CSV to a ROM.

Supports using either the Spanish column (for ES mimic) or the translation column (FR).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.text_reinserter import SmartReinserter


def _find_latest(path: Path, pattern: str) -> Optional[Path]:
    if not path.exists():
        return None
    candidates = list(path.glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _load_english_pointer_map(path: Path) -> Dict[int, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    mapping: Dict[int, dict] = {}
    for item in data.get('texts', []):
        offset = item.get('offset')
        if isinstance(offset, int):
            mapping[offset] = item
    return mapping


def _parse_int(value: str) -> Optional[int]:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Apply dynamic diff CSV translations to a ROM.'
    )
    parser.add_argument('--csv', type=Path, help='Dynamic diff CSV path')
    parser.add_argument('--rom', type=Path, required=True, help='Source ROM to patch')
    parser.add_argument('--output', type=Path, help='Output ROM (defaults to in-place)')
    parser.add_argument(
        '--column',
        choices=['spanish_text', 'translation'],
        default='translation',
        help='CSV column to use as translation source',
    )
    parser.add_argument(
        '--english-texts',
        type=Path,
        default=Path('output/extracted/extracted_texts/englishrom_texts.json'),
        help='English extraction JSON (pointer offsets)',
    )
    parser.add_argument('--allow-relocate', action='store_true', default=True)
    parser.add_argument('--allow-truncate', action='store_true', default=False)
    parser.add_argument('--require-100', action='store_true', help='Fail if not 100% inserted')

    args = parser.parse_args()

    csv_path = args.csv
    if csv_path is None:
        translation_dir = Path('output/translation')
        csv_path = _find_latest(translation_dir, '*_dynamic_diff_translation.csv')
    if csv_path is None or not csv_path.exists():
        print('Error: dynamic diff CSV not found.')
        return 1

    if not args.rom.exists():
        print(f'Error: ROM not found: {args.rom}')
        return 1

    output_path = args.output or args.rom
    english_map = _load_english_pointer_map(args.english_texts)

    translations: List[dict] = []
    with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw_offset = row.get('offset') or ''
            if not raw_offset:
                continue
            offset = int(raw_offset.replace('0x', ''), 16)
            translation = (row.get(args.column) or '').strip()
            if not translation:
                continue

            entry = {
                'offset': offset,
                'translation': translation,
                'encoding': row.get('encoding') or 'pokemon',
                'original_length': _parse_int(row.get('original_length') or ''),
                'padding_available': _parse_int(row.get('padding_available') or ''),
                'category': row.get('category') or '',
            }

            pointer_offsets = english_map.get(offset, {}).get('pointer_offsets')
            if pointer_offsets:
                entry['pointer_offsets'] = pointer_offsets

            translations.append(entry)

    if not translations:
        print('No translations found to apply.')
        return 1

    rom_data = bytearray(args.rom.read_bytes())
    reinserter = SmartReinserter(
        rom_data,
        allow_truncate=args.allow_truncate,
        allow_relocate=args.allow_relocate,
    )

    for translation in translations:
        reinserter.reinsert_text(translation)

    report = reinserter.get_report()
    stats = report['statistics']

    output_path.write_bytes(rom_data)

    print(f'CSV: {csv_path}')
    print(f'ROM: {args.rom} -> {output_path}')
    print(
        'Inserted: {successful}/{total} (skipped too long: {skipped}, relocation failed: {rel_fail})'.format(
            successful=stats['successful'],
            total=stats['total_texts'],
            skipped=stats['skipped_too_long'],
            rel_fail=stats['relocation_failed'],
        )
    )

    if args.require_100 and (
        stats['successful'] != stats['total_texts']
        or stats['failed'] != 0
        or stats['skipped_too_long'] != 0
        or stats['relocation_failed'] != 0
    ):
        print('Error: insertion did not reach 100%.')
        return 2

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
