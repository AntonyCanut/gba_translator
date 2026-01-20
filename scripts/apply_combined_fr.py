#!/usr/bin/env python3
"""
Apply translations from combined_fr.txt into a trilingual CSV.

Updates the "translation" column for matching offsets only.
Optionally extends the CSV with missing offsets from combined_fr.

Escapes:
- "\\n" -> newline
- "\\l" -> "<0xFA>"
- "\\p" -> "<0xFB>"

Normalization:
- Curly quotes, ellipsis, ligatures, and non-breaking spaces are normalized.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.padding_detector import PaddingDetector
from src.core.rom_reader import ROMReader
from src.core.text_converter import JSONToCSVConverter


LINE_RE = re.compile(r'^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$')
PLACEHOLDER_RE = re.compile(r'\{[^}]+\}')
CONTROL_TOKEN_RE = re.compile(r'<0xFD><0x[0-9A-Fa-f]{2}>')
TYPO_FIXES = {
    '’': "'",
    '“': '"',
    '”': '"',
    '«': '"',
    '»': '"',
    '…': '...',
    'œ': 'oe',
    'Œ': 'OE',
    '\u00A0': ' ',
}


def _parse_offset(value: str) -> int:
    text = value.strip()
    if text.lower().startswith('0x'):
        return int(text[2:], 16)
    return int(text, 16) if all(c in '0123456789abcdefABCDEF' for c in text) else int(text)


def _normalize_text(text: str) -> str:
    normalized = (
        text.replace('\\n', '\n')
            .replace('\\l', '<0xFA>')
            .replace('\\p', '<0xFB>')
    )
    for src, dst in TYPO_FIXES.items():
        normalized = normalized.replace(src, dst)
    return normalized


def _apply_placeholder_mapping(text: str, reference: str) -> str:
    placeholders = PLACEHOLDER_RE.findall(text)
    if not placeholders:
        return text
    tokens = CONTROL_TOKEN_RE.findall(reference)
    if not tokens or len(tokens) != len(placeholders):
        return text
    result = text
    for placeholder, token in zip(placeholders, tokens):
        result = result.replace(placeholder, token, 1)
    return result


def _load_combined(path: Path) -> Tuple[Dict[int, str], int]:
    mapping: Dict[int, str] = {}
    skipped = 0
    with path.open('r', encoding='utf-8') as handle:
        for line in handle:
            line = line.rstrip('\n')
            if not line.strip():
                continue
            match = LINE_RE.match(line)
            if not match:
                skipped += 1
                continue
            offset = int(match.group(1), 16)
            text = _normalize_text(match.group(2))
            mapping[offset] = text
    return mapping, skipped


def _load_csv(path: Path) -> Tuple[List[dict], List[str]]:
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError('CSV is missing header row.')
        rows = list(reader)
        return rows, reader.fieldnames


def _write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_extracted_map(path: Path) -> Dict[int, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    mapping: Dict[int, dict] = {}
    for item in data.get('texts', []):
        offset = item.get('offset')
        if isinstance(offset, int):
            mapping[offset] = item
    return mapping


def _length_without_terminator(entry: dict) -> int:
    byte_length = entry.get('byte_length') or entry.get('length')
    if byte_length is None:
        return max(len(entry.get('text', '')), 0)
    try:
        return max(int(byte_length) - 1, 0)
    except (TypeError, ValueError):
        return max(len(entry.get('text', '')), 0)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Apply combined_fr.txt translations to trilingual CSV.'
    )
    parser.add_argument(
        '--combined',
        type=Path,
        default=Path('combined_fr.txt'),
        help='Path to combined_fr.txt',
    )
    parser.add_argument(
        '--csv',
        type=Path,
        default=Path('output/translation/2026-01-15_trilingual_translation.csv'),
        help='Path to trilingual CSV',
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Optional output CSV path (defaults to --csv, in-place)',
    )
    parser.add_argument(
        '--extend',
        action='store_true',
        help='Add missing combined offsets to the CSV',
    )
    parser.add_argument(
        '--english',
        type=Path,
        default=Path('output/extracted/extracted_texts/englishrom_texts.json'),
        help='English extraction JSON (for --extend)',
    )
    parser.add_argument(
        '--spanish',
        type=Path,
        default=Path('output/extracted/extracted_texts/spanishrom_texts.json'),
        help='Spanish extraction JSON (for --extend)',
    )
    parser.add_argument(
        '--rom',
        type=Path,
        default=Path('input/roms/englishrom.gba'),
        help='English ROM (padding detection for --extend)',
    )
    args = parser.parse_args()

    if not args.combined.exists():
        print(f'Error: combined file not found: {args.combined}')
        return 1
    if not args.csv.exists():
        print(f'Error: CSV file not found: {args.csv}')
        return 1

    combined_map, skipped = _load_combined(args.combined)
    rows, fieldnames = _load_csv(args.csv)

    if 'offset' not in fieldnames or 'translation' not in fieldnames:
        print('Error: CSV must include offset and translation columns.')
        return 1

    updated = 0
    matched = 0
    csv_offsets = set()
    for row in rows:
        try:
            offset = _parse_offset(row['offset'])
        except ValueError:
            continue
        csv_offsets.add(offset)
        if offset in combined_map:
            matched += 1
            text = combined_map[offset]
            if text:
                reference = row.get('original_text', '')
                text = _apply_placeholder_mapping(text, reference)
                row['translation'] = text
                updated += 1

    added = 0
    missing_english = 0
    missing_spanish = 0
    if args.extend:
        english_map = _load_extracted_map(args.english)
        spanish_map = _load_extracted_map(args.spanish)
        if not english_map:
            print(f'Error: English extraction missing or empty: {args.english}')
            return 1

        detector = None
        if args.rom.exists():
            rom_reader = ROMReader(str(args.rom))
            rom_reader.load()
            detector = PaddingDetector(rom_reader)

        converter = JSONToCSVConverter()
        for offset, translation in combined_map.items():
            if offset in csv_offsets:
                continue
            entry = english_map.get(offset)
            if not entry:
                missing_english += 1
                continue

            text = entry.get('decoded_text') or entry.get('text') or ''
            encoding = entry.get('encoding', 'pokemon')
            length = _length_without_terminator(entry)
            padding = 0
            if detector:
                padding = detector.detect_padding(offset, length, extended_search=True)
            real_max = length + padding

            translation = _apply_placeholder_mapping(translation, text)

            spanish_entry = spanish_map.get(offset)
            if spanish_entry is None and args.spanish.exists():
                missing_spanish += 1
            spanish_text = ''
            if spanish_entry:
                spanish_text = spanish_entry.get('decoded_text') or spanish_entry.get('text') or ''

            rows.append({
                'offset': f'0x{offset:08X}',
                'original_text': text,
                'spanish_text': spanish_text,
                'original_length': length,
                'padding_available': padding,
                'real_max_length': real_max,
                'encoding': encoding,
                'category': converter.categorize_text(text, offset),
                'translation': translation,
                'notes': '',
            })
            csv_offsets.add(offset)
            added += 1

        rows.sort(key=lambda row: _parse_offset(row['offset']))

    output_path = args.output or args.csv
    _write_csv(output_path, rows, fieldnames)

    print(f'Combined entries: {len(combined_map)} (skipped lines: {skipped})')
    print(f'CSV rows matched: {matched} (updated: {updated})')
    if args.extend:
        print(f'CSV rows added: {added}')
        if missing_english:
            print(f'Offsets missing in English extraction: {missing_english}')
        if args.spanish.exists() and missing_spanish:
            print(f'Offsets missing in Spanish extraction: {missing_spanish}')
    print(f'CSV written: {output_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
