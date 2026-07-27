#!/usr/bin/env python3
"""
Generate a translation_ready.json from combined_fr.txt + English extraction.

Bypasses the trilingual CSV step for CI builds where no pre-built CSV exists.
Run via `make prepare-fr` before `make build-fr`.

The generated JSON is date-stamped (YYYY-MM-DD_translation_ready.json) so it is
picked up automatically by the existing FR_TRANSLATION glob in the Makefile.

Usage:
    python3 scripts/prepare_fr_json.py
    python3 scripts/prepare_fr_json.py \\
        --combined languages/fr/combined_fr.txt \\
        --english output/extracted/extracted_texts/englishrom_texts.json
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/ for sibling import

from src.core.text_codec import TextDecoder, TextEncoder
from src.core.text_converter import JSONToCSVConverter
from languages.fr.dedicated_patch_offsets import (
    GENERIC_TRANSLATION_OFFSETS as DEDICATED_PATCH_OFFSETS,
)

# Offsets owned by dedicated, byte-exact post-build patches that the generic
# builder must NOT touch. The arrow-prefixed World-Map junction panels are seen
# by the extractor as 1-byte strings (leading 0x79–0x7C arrow), so they arrive
# here with original_length==1 and a much longer FR → too_long → the generic
# relocator moves *and* reflows them, destroying the arrow-at-line-start layout
# and the contiguous fragments that patch_worldmap_junction_panels_fr.py
# verifies. Leaving the EN original in place lets each dedicated patch own it.

# Identical to apply_combined_fr.py so both scripts treat the source file the same way
LINE_RE = re.compile(r'^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$')
TYPO_FIXES: Dict[str, str] = {
    '‘': "'",   # left single quotation mark
    '’': "'",   # right single quotation mark (apostrophe)
    '“': '"',   # left double quotation mark
    '”': '"',   # right double quotation mark
    '«': '"',   # left guillemet «
    '»': '"',   # right guillemet »
    '…': '...',  # ellipsis
    'œ': 'oe',  # œ
    'Œ': 'OE',  # Œ
    ' ': ' ',   # non-breaking space
}


def _normalize_text(text: str) -> str:
    result = (
        text.replace('\\n', '\n')
            .replace('\\l', '<0xFA>')
            .replace('\\p', '<0xFB>')
    )
    for src, dst in TYPO_FIXES.items():
        result = result.replace(src, dst)
    return result


def _load_combined(path: Path) -> Dict[int, str]:
    """Parse combined_fr.txt; last entry wins for duplicate offsets."""
    mapping: Dict[int, str] = {}
    with path.open('r', encoding='utf-8') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line.strip() or line.strip().startswith('#'):
                continue
            m = LINE_RE.match(line)
            if not m:
                continue
            offset = int(m.group(1), 16)
            text = _normalize_text(m.group(2))
            if text:
                mapping[offset] = text
    return mapping


def _load_english_map(path: Path) -> Dict[int, dict]:
    data = json.loads(path.read_text(encoding='utf-8'))
    result: Dict[int, dict] = {}
    for item in data.get('texts', []):
        offset = item.get('offset')
        if isinstance(offset, int):
            result[offset] = item
    return result


def _encoded_length(text: str, encoding: str = 'pokemon') -> int:
    """Return the encoded byte count excluding the 0xFF terminator."""
    try:
        return max(len(TextEncoder.encode(text, encoding)) - 1, 0)
    except Exception:
        return len(text)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Generate translation_ready.json from combined_fr.txt + EN extraction.',
    )
    parser.add_argument(
        '--combined',
        type=Path,
        default=Path('languages/fr/combined_fr.txt'),
        help='Master FR translation file (default: languages/fr/combined_fr.txt)',
    )
    parser.add_argument(
        '--english',
        type=Path,
        default=Path('output/extracted/extracted_texts/englishrom_texts.json'),
        help='English extraction JSON (default: output/extracted/extracted_texts/englishrom_texts.json)',
    )
    parser.add_argument(
        '--critical',
        type=Path,
        default=Path('languages/fr/data/critical_strings_fr.txt'),
        help='Critical-strings guard file; entries override combined_fr.txt',
    )
    parser.add_argument(
        '--english-rom',
        type=Path,
        default=Path('input/roms/englishrom.gba'),
        help='English ROM for no-pointer in-place fallback (default: input/roms/englishrom.gba)',
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        help='Output path (default: output/translation/YYYY-MM-DD_translation_ready.json)',
    )
    args = parser.parse_args()

    if not args.combined.exists():
        print(f'Error: combined file not found: {args.combined}')
        return 1
    if not args.english.exists():
        print(f'Error: English extraction not found: {args.english}')
        print('Run `make extract` or `make build-fr` first to generate it.')
        return 1

    print(f'Loading {args.combined} ...')
    fr_map = _load_combined(args.combined)
    print(f'  {len(fr_map)} FR entries (after dedup, last-wins)')

    if args.critical.exists():
        critical = _load_combined(args.critical)
        fr_map.update(critical)
        print(f'  {len(critical)} critical overrides applied from {args.critical}')

    print(f'Loading {args.english} ...')
    en_map = _load_english_map(args.english)
    print(f'  {len(en_map)} English entries')

    categorizer = JSONToCSVConverter()
    translations = []
    missing_en = 0
    excluded_dedicated = 0

    for offset in sorted(fr_map):
        if offset in DEDICATED_PATCH_OFFSETS:
            # Owned by a dedicated post-build patch — leave the EN original in
            # place so the generic relocator does not re-wrap it.
            excluded_dedicated += 1
            continue
        fr_text = fr_map[offset]
        en_entry = en_map.get(offset)
        if not en_entry:
            missing_en += 1
            continue

        original_text = en_entry.get('decoded_text') or en_entry.get('text') or ''
        byte_length = en_entry.get('byte_length') or en_entry.get('length') or 0
        original_length = max(int(byte_length) - 1, 0)
        encoding = en_entry.get('encoding', 'pokemon')

        fr_length = _encoded_length(fr_text, encoding)
        category = categorizer.categorize_text(original_text, offset)

        translations.append({
            'offset': offset,
            'original_text': original_text,
            'translation': fr_text,
            'length': fr_length,
            'original_length': original_length,
            'padding_used': fr_length - original_length,
            'encoding': encoding,
            'category': category,
            'notes': '',
            'too_long': fr_length > original_length,
        })

    # Fallback: for offsets absent from the EN extraction, read the ROM directly.
    # These are inline texts with no GBA pointer — they must be injected in-place,
    # so we only include them when the FR encoding fits within the EN byte count.
    nopoi_added = 0
    nopoi_skipped_long = 0
    if missing_en > 0 and args.english_rom.exists():
        rom_bytes = args.english_rom.read_bytes()
        rom_size = len(rom_bytes)
        for offset in sorted(fr_map):
            if offset in DEDICATED_PATCH_OFFSETS:
                continue
            if en_map.get(offset):
                continue
            fr_text = fr_map[offset]
            if not fr_text or offset >= rom_size:
                continue
            # Read EN string until the CFRU terminator (0xFF).
            end = offset
            while end < rom_size and rom_bytes[end] != 0xFF:
                end += 1
            en_len = end - offset
            # Require at least 3 bytes (e.g. "OK\xff") to avoid patching garbage.
            if en_len < 3:
                continue
            fr_length = _encoded_length(fr_text, 'pokemon')
            if fr_length == 0 or fr_length > en_len:
                nopoi_skipped_long += 1
                continue
            en_raw = bytes(rom_bytes[offset:end + 1])
            original_text = TextDecoder.decode_pokemon(en_raw, preserve_unknown=True)
            category = categorizer.categorize_text(original_text, offset)
            translations.append({
                'offset': offset,
                'original_text': original_text,
                'english_raw_bytes': en_raw.hex(),
                'translation': fr_text,
                'length': fr_length,
                'original_length': en_len,
                'padding_used': fr_length - en_len,
                'encoding': 'pokemon',
                'category': category,
                'notes': 'no-pointer: in-place only',
                'too_long': False,
            })
            nopoi_added += 1
        missing_en -= nopoi_added

    output_path = args.output
    if output_path is None:
        date_str = datetime.now().strftime('%Y-%m-%d')
        output_path = Path('output/translation') / f'{date_str}_translation_ready.json'

    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        'conversion_date': datetime.now().isoformat(),
        'source_csv': str(args.combined),
        'total_translations': len(translations),
        'total_errors': 0,
        'total_warnings': missing_en,
        'translations': translations,
    }

    with open(output_path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False)

    print(f'\n✓ {len(translations)} translations written to {output_path}')
    if excluded_dedicated:
        print(f'  ({excluded_dedicated} offsets left to dedicated post-build patches)')
    if nopoi_added:
        print(f'  ({nopoi_added} no-pointer in-place entries recovered from ROM)')
    if nopoi_skipped_long:
        print(f'  ({nopoi_skipped_long} no-pointer entries skipped: FR too long for in-place)')
    if missing_en:
        print(f'  ({missing_en} offsets from combined_fr.txt had no matching EN entry — skipped)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
