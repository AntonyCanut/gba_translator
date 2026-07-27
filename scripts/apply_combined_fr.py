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
from languages.fr.dedicated_patch_offsets import GENERIC_TRANSLATION_OFFSETS


LINE_RE = re.compile(r'^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$')
PLACEHOLDER_RE = re.compile(r'\{[^}]+\}')
CONTROL_TOKEN_RE = re.compile(r'<0xFD><0x[0-9A-Fa-f]{2}>')
CONTROL_TOKEN_CODE_RE = re.compile(r'<0xFD><0x([0-9A-Fa-f]{2})>')
# Named "<0xFD><0xNN>" script/battle variables (docs/17_TEXT_VARIABLES.md)
# carry one fixed code each. Mirrors the same table in
# src/translators/19_build_translated_rom_generic.py — resolving a
# placeholder by name instead of by its position in the translation lets a
# translation legitimately reorder two variables (e.g. French swapping
# "{ability} de {name}" versus English "{name}'s {ability}") without handing
# the wrong control code to the wrong placeholder.
FD_VARIABLE_CODES = {
    'PLAYER': 0x01,
    'STR_VAR_1': 0x02,
    'STR_VAR_2': 0x03,
    'STR_VAR_3': 0x04,
    'KUN': 0x05,
    'RIVAL': 0x06,
    'VERSION': 0x07,
    'EVIL_TEAM': 0x08,
    'GOOD_TEAM': 0x09,
    'EVIL_LEADER': 0x0A,
    'GOOD_LEADER': 0x0B,
    'EVIL_LEGENDARY': 0x0C,
    'B_ATK_NAME_WITH_PREFIX': 0x0F,
    'B_DEF_NAME_WITH_PREFIX': 0x10,
    'B_EFF_NAME_WITH_PREFIX': 0x11,
    'B_ACTIVE_NAME_WITH_PREFIX': 0x12,
    'B_SCR_ACTIVE_NAME_WITH_PREFIX': 0x13,
    'B_CURRENT_MOVE': 0x14,
    'B_LAST_ITEM': 0x16,
    'B_ATK_ABILITY': 0x18,
    'B_DEF_ABILITY': 0x19,
    'B_SCR_ACTIVE_ABILITY': 0x1A,
    'B_TRAINER1_CLASS': 0x1C,
    'B_TRAINER1_NAME': 0x1D,
    'B_LINK_PARTNER_NAME': 0x1F,
    'B_LINK_OPPONENT1_NAME': 0x20,
    'B_LINK_OPPONENT2_NAME': 0x21,
    'B_TRAINER2_LOSE_TEXT': 0x2E,
    'B_TRAINER2_WIN_TEXT': 0x2F,
}
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
    remaining = list(tokens)
    unresolved: List[str] = []
    result = text
    for placeholder in placeholders:
        code = FD_VARIABLE_CODES.get(placeholder[1:-1])
        token = None
        if code is not None:
            for idx, candidate in enumerate(remaining):
                match = CONTROL_TOKEN_CODE_RE.match(candidate)
                if match and int(match.group(1), 16) == code:
                    token = remaining.pop(idx)
                    break
        if token is None:
            unresolved.append(placeholder)
            continue
        result = result.replace(placeholder, token, 1)
    for placeholder in unresolved:
        if not remaining:
            break
        token = remaining.pop(0)
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


def _load_critical(path: Path) -> Dict[int, str]:
    """Load the critical-strings guard file (lines starting with # are comments)."""
    mapping: Dict[int, str] = {}
    if not path.exists():
        return mapping
    with path.open('r', encoding='utf-8') as handle:
        for line in handle:
            line = line.rstrip('\n')
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            match = LINE_RE.match(line)
            if not match:
                continue
            offset = int(match.group(1), 16)
            text = _normalize_text(match.group(2))
            mapping[offset] = text
    return mapping


def _load_csv(path: Path) -> Tuple[List[dict], List[str]]:
    with path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError('CSV is missing header row.')
        rows = list(reader)
        return rows, reader.fieldnames


def _dedicated_offsets_for_combined(path: Path) -> frozenset[int]:
    """Les exclusions post-build sont propres à la source française."""
    if path.parent.name.lower() == "fr":
        return GENERIC_TRANSLATION_OFFSETS
    return frozenset()


def _exclude_dedicated_offsets(
    combined_map: Dict[int, str],
    rows: List[dict],
    dedicated_offsets: frozenset[int] = GENERIC_TRANSLATION_OFFSETS,
) -> int:
    """Retirer les offsets post-build et effacer toute valeur CSV obsolète."""
    excluded = 0
    for offset in dedicated_offsets:
        if offset in combined_map:
            del combined_map[offset]
            excluded += 1

    for row in rows:
        try:
            offset = _parse_offset(row.get("offset", ""))
        except (TypeError, ValueError):
            continue
        if offset in dedicated_offsets:
            row["translation"] = ""
    return excluded


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
        default=Path('languages/fr/combined_fr.txt'),
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
    parser.add_argument(
        '--critical',
        type=Path,
        default=Path('languages/fr/data/critical_strings_fr.txt'),
        help='Critical-strings guard file (entries always override combined_fr.txt)',
    )
    args = parser.parse_args()

    if not args.combined.exists():
        print(f'Error: combined file not found: {args.combined}')
        return 1
    if not args.csv.exists():
        print(f'Error: CSV file not found: {args.csv}')
        return 1

    combined_map, skipped = _load_combined(args.combined)

    # Critical strings always take highest priority — they override combined_fr.txt
    # and cannot be accidentally dropped by future edits to that file.
    critical_map = _load_critical(args.critical)
    if critical_map:
        combined_map.update(critical_map)
        print(f'Critical strings applied: {len(critical_map)} (from {args.critical})')
    rows, fieldnames = _load_csv(args.csv)
    excluded_dedicated = _exclude_dedicated_offsets(
        combined_map,
        rows,
        _dedicated_offsets_for_combined(args.combined),
    )

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
    if excluded_dedicated:
        print(f'Dedicated post-build offsets excluded: {excluded_dedicated}')
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
