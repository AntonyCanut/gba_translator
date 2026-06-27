#!/usr/bin/env python3
"""
Audit the French translation (combined_fr.txt + trilingual CSV).

Categories reported:
- byte_image: characters that are JP/INTL-decoded raw bytes (kana, fullwidth,
  byte-image uppercase glued to kana) — they corrupt ROM data when re-encoded.
- unencodable: characters the Pokemon encoder turns into '?' in-game.
- untranslated: lines still in English.
- placeholder_orphan: {X} placeholders with no control sequence in the
  English reference text (would be written literally).
- overflow: visual lines longer than the textbox limit.

Usage:
    python3 scripts/audit_translation_fr.py [--strict]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.text_codec import TextDecoder, TextEncoder

LINE_RE = re.compile(r'^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$')
# {COLOR}X carries its color-code char: strip both (consumed by the builder).
COLOR_MARKER_RE = re.compile(r'\{COLOR\}.?')
PLACEHOLDER_RE = re.compile(r'\{[^}]+\}')
HEX_TOKEN_RE = re.compile(r'<0x[0-9A-Fa-f]{2}>')
KANA_RE = re.compile(r'[぀-ゟ゠-ヿ]')
FULLWIDTH_RE = re.compile(r'[＀-￯　-〿]')
CONTROL_SEQ_RE = re.compile(r'<0x(?:FD|FC|F7|F8|F9)>', re.I)

EN_WORDS_RE = re.compile(
    r'\b(the|you|your|is|are|was|were|have|has|will|can|with|and|that|this|'
    r'what|when|where|why|how|lost|used|found|battle|trainer|received|wants|'
    r'would|should|my|here|there|not)\b'
)
FR_HINTS_RE = re.compile(
    r'\b(le|la|les|une|des|est|sont|je|tu|il|elle|nous|vous|que|qui|pas|'
    r'avec|pour|dans|sur|ton|ta|tes|mon|ma|mes|du|et|en|au|aux)\b'
    r'|[àâçèéêëîïôùûœ]'
)

MAX_VISUAL_LINE = 42


def visible_text(text: str) -> str:
    cleaned = COLOR_MARKER_RE.sub(' ', text)
    cleaned = PLACEHOLDER_RE.sub(' ', cleaned)
    cleaned = HEX_TOKEN_RE.sub(' ', cleaned)
    return cleaned.replace('\\n', '\n').replace('\\l', '\n').replace('\\p', '\n')


def is_english(text: str) -> bool:
    visible = visible_text(text).lower()
    en_hits = len(EN_WORDS_RE.findall(visible))
    fr_hits = len(FR_HINTS_RE.findall(visible))
    return en_hits >= 2 and en_hits > fr_hits


def unencodable_chars(text: str) -> set[str]:
    visible = COLOR_MARKER_RE.sub('', text)
    visible = PLACEHOLDER_RE.sub('', visible)
    visible = HEX_TOKEN_RE.sub('', visible)
    visible = visible.replace('\\n', '\n').replace('\\l', '').replace('\\p', '')
    encoded = TextEncoder.encode_pokemon(visible)
    decoded = TextDecoder.decode_pokemon(encoded)
    source_questions = visible.count('?') + visible.count('？')
    if decoded.count('?') <= source_questions:
        return set()
    bad = set()
    for ch in visible:
        if ch in ('\n', '?', '？'):
            continue
        roundtrip = TextDecoder.decode_pokemon(TextEncoder.encode_pokemon(ch))
        if '?' in roundtrip:
            bad.add(ch)
    return bad


def overflow_lines(text: str) -> list[str]:
    flat = PLACEHOLDER_RE.sub('@@@@@@', text)
    flat = HEX_TOKEN_RE.sub('', flat)
    chunks = re.split(r'\\[nlp]', flat)
    return [c for c in chunks if len(c) > MAX_VISUAL_LINE]


def load_combined(path: Path) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for raw in path.open(encoding='utf-8'):
        match = LINE_RE.match(raw.rstrip('\n'))
        if match:
            mapping[int(match.group(1), 16)] = match.group(2)
    return mapping


def load_english(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    return {
        t['offset']: t.get('text', '')
        for t in data.get('texts', [])
        if isinstance(t.get('offset'), int)
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit French translation quality.')
    parser.add_argument('--combined', type=Path, default=Path('languages/fr/combined_fr.txt'))
    parser.add_argument(
        '--english',
        type=Path,
        default=Path('output/extracted/extracted_texts/englishrom_texts.json'),
    )
    parser.add_argument(
        '--report',
        type=Path,
        default=Path('output/reports/translation_fr_audit.json'),
    )
    parser.add_argument('--strict', action='store_true',
                        help='Exit 1 when corrupting issues are found')
    args = parser.parse_args()

    combined = load_combined(args.combined)
    english = load_english(args.english)

    issues: dict[str, list[dict]] = {
        'byte_image': [],
        'unencodable': [],
        'untranslated': [],
        'placeholder_orphan': [],
        'overflow': [],
    }

    for offset, text in sorted(combined.items()):
        if KANA_RE.search(text) or FULLWIDTH_RE.search(text):
            issues['byte_image'].append({'offset': f'0x{offset:X}', 'text': text[:120]})
            continue

        bad = unencodable_chars(text)
        if bad:
            issues['unencodable'].append({
                'offset': f'0x{offset:X}',
                'chars': sorted(bad),
                'text': text[:120],
            })

        if is_english(text):
            issues['untranslated'].append({'offset': f'0x{offset:X}', 'text': text[:120]})

        placeholders = PLACEHOLDER_RE.findall(text)
        if placeholders:
            reference = english.get(offset, '')
            if reference and not CONTROL_SEQ_RE.search(reference):
                issues['placeholder_orphan'].append({
                    'offset': f'0x{offset:X}',
                    'placeholders': placeholders,
                    'text': text[:120],
                })

        long_lines = overflow_lines(text)
        if long_lines:
            issues['overflow'].append({
                'offset': f'0x{offset:X}',
                'lines': long_lines[:3],
            })

    print('=' * 60)
    print('FR translation audit — combined_fr.txt')
    print('=' * 60)
    print(f'Entries analyzed       : {len(combined)}')
    for key, label in (
        ('byte_image', 'Byte-images (kana/fullwidth) — corrupt the ROM'),
        ('unencodable', "Unencodable characters (will display as '?')"),
        ('untranslated', 'Probably untranslated (English)'),
        ('placeholder_orphan', 'Placeholders without EN control sequence'),
        ('overflow', f'Visual lines > {MAX_VISUAL_LINE} characters'),
    ):
        print(f'{label:52s}: {len(issues[key])}')

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(issues, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f'\nReport: {args.report}')

    corrupting = len(issues['byte_image']) + len(issues['unencodable'])
    if args.strict and corrupting:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
