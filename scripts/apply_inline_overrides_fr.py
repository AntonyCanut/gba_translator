#!/usr/bin/env python3
"""
Apply French inline overrides (no pointers) using Spanish inline diffs.

This mirrors the Spanish approach: inline texts are stored at the same offsets
and differ from English without pointer tables. We detect those offsets by
comparing English vs Spanish raw inline text and patch the built FR ROM only
when a combined_fr translation exists.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.dialogue_linewrap import rewrap as rewrap_dialogue
from src.core.fixed_tables import in_fixed_table
from src.core.padding_detector import PaddingDetector
from src.core.rom_reader import ROMReader
from src.core.text_codec import TextDecoder, TextEncoder
from src.core.text_converter import JSONToCSVConverter


LINE_RE = re.compile(r'^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$')
PLACEHOLDER_RE = re.compile(r'\{[^}]+\}')
CONTROL_TOKEN_RE = re.compile(r'<0x([0-9A-Fa-f]{2})>')
COLOR_MARKER_RE = re.compile(r'\{COLOR\}(.?)')
DYNAMIC_GROUP_RE = re.compile(
    r'(?:<0xFD><0x[0-9A-Fa-f]{2}>)(?:\s+<0xFD><0x[0-9A-Fa-f]{2}>)*'
)
GROUP_PLACEHOLDER = '<<VAR>>'

TYPO_FIXES = {
    '\u2019': "'",
    '\u201c': '"',
    '\u201d': '"',
    '\u00ab': '"',
    '\u00bb': '"',
    '\u2026': '...',
    '\u0153': 'oe',
    '\u0152': 'OE',
    '\u00a0': ' ',
}

CONTROL_PREFIXES = {0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD}
ARG_CONSUME_PREFIXES = {0xF7, 0xFC}
RAW_ARG_PREFIXES = {0xF7: 1, 0xF8: 1, 0xF9: 1, 0xFD: 1}
# Argument bytes per FC extended control command (Gen III ExtCtrlCode):
# COLOR_HIGHLIGHT_SHADOW (0x04) takes 3, PLAY_BGM/PLAY_SE take a 16-bit
# id, the other display commands take one byte or none. Truncating these
# (the old 1-arg-only table) corrupted strings like the battle menu.
FC_ARG_COUNTS = {
    0x01: 1, 0x02: 1, 0x03: 1, 0x04: 3, 0x05: 1, 0x06: 1,
    0x08: 1, 0x0B: 2, 0x0C: 1, 0x0D: 1, 0x0E: 1, 0x10: 2,
    0x11: 1, 0x12: 1, 0x13: 1, 0x14: 1, 0x19: 1,
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


def _normalize_whitespace(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


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


def _load_translation_offsets(path: Optional[Path]) -> set[int]:
    if not path or not path.exists():
        return set()
    data = json.loads(path.read_text(encoding='utf-8'))
    return {item['offset'] for item in data.get('translations', []) if 'offset' in item}


def _load_translation_items(path: Optional[Path]) -> List[dict]:
    if not path or not path.exists():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    return list(data.get('translations', []))


def _load_extracted_map(path: Optional[Path]) -> Dict[int, dict]:
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    mapping: Dict[int, dict] = {}
    for item in data.get('texts', []):
        offset = item.get('offset')
        if isinstance(offset, int):
            mapping[offset] = item
    return mapping


def _group_dynamic_tokens(text: str) -> Tuple[str, List[str]]:
    groups: List[str] = []

    def repl(match: re.Match) -> str:
        groups.append(match.group(0))
        return GROUP_PLACEHOLDER

    templated = DYNAMIC_GROUP_RE.sub(repl, text)
    templated = _normalize_whitespace(templated)
    return templated, groups


def _build_template_map(items: List[dict]) -> Dict[str, str]:
    templates: Dict[str, str] = {}
    for item in items:
        original = (
            item.get('original_text')
            or item.get('english_text')
            or item.get('text')
            or ''
        )
        translation = item.get('translation') or ''
        if not original or not translation:
            continue
        key, key_groups = _group_dynamic_tokens(original)
        if not key_groups:
            continue
        value, value_groups = _group_dynamic_tokens(translation)
        if not key or not value:
            continue
        if len(key_groups) != len(value_groups):
            continue
        templates.setdefault(key, value)
    return templates


def _scan_control_tokens(text: str) -> List[Tuple[int, int, int]]:
    return [
        (int(match.group(1), 16), match.start(), match.end())
        for match in CONTROL_TOKEN_RE.finditer(text)
    ]


def _extract_control_sequences_from_raw(raw_bytes: bytes) -> List[List[int]]:
    sequences: List[List[int]] = []
    i = 0
    while i < len(raw_bytes):
        value = raw_bytes[i]
        if value == 0xFF:
            break
        if value == 0xFC:
            if i + 1 < len(raw_bytes):
                cmd = raw_bytes[i + 1]
                arg_count = FC_ARG_COUNTS.get(cmd, 0)
                args = list(raw_bytes[i + 2:i + 2 + arg_count])
                sequences.append([value, cmd] + args)
                i += 2 + len(args)
            else:
                sequences.append([value])
                i += 1
            continue
        if value in CONTROL_PREFIXES:
            seq = [value]
            arg_len = RAW_ARG_PREFIXES.get(value, 0)
            if arg_len and i + 1 < len(raw_bytes):
                seq.append(raw_bytes[i + 1])
                i += 2
            else:
                i += 1
            sequences.append(seq)
            continue
        i += 1
    return sequences


def _format_sequence(tokens: List[int]) -> str:
    return ''.join(f"<0x{b:02X}>" for b in tokens)


def _extract_control_sequences(
    text: str,
    raw_bytes_hex: Optional[str] = None,
) -> Tuple[List[List[int]], List[List[int]]]:
    sequences: List[List[int]] = []
    if raw_bytes_hex:
        try:
            raw_bytes = bytes.fromhex(raw_bytes_hex)
        except ValueError:
            raw_bytes = b''
        sequences = _extract_control_sequences_from_raw(raw_bytes)

    if not sequences:
        tokens = _scan_control_tokens(text)
        i = 0
        while i < len(tokens):
            value, start, end = tokens[i]
            if value not in CONTROL_PREFIXES:
                i += 1
                continue

            if value == 0xFC:
                seq = [value]
                if i + 1 < len(tokens) and end == tokens[i + 1][1]:
                    seq.append(tokens[i + 1][0])
                    if i + 2 < len(tokens) and tokens[i + 1][2] == tokens[i + 2][1]:
                        seq.append(tokens[i + 2][0])
                        i += 3
                    else:
                        i += 2
                else:
                    i += 1
                sequences.append(seq)
                continue

            seq = [value]
            if i + 1 < len(tokens) and end == tokens[i + 1][1]:
                seq.append(tokens[i + 1][0])
                i += 2
            else:
                i += 1
            sequences.append(seq)

    color_sequences: List[List[int]] = []
    other_sequences: List[List[int]] = []
    for seq in sequences:
        if seq[0] == 0xFC and len(seq) == 3 and seq[1] == 0x01:
            color_sequences.append(seq)
        else:
            other_sequences.append(seq)
    return color_sequences, other_sequences


def _strip_accents(ch: str) -> str:
    return unicodedata.normalize('NFD', ch)[:1]


def _argument_glyphs(seq: List[int]) -> List[str]:
    """Printable glyphs the decoder emitted for a sequence's arguments.

    For an FC control the command byte (``seq[1]``) never appears in the
    decoded text (it has no charmap glyph); only argument bytes that
    decode to a printable character were rendered after the placeholder,
    and only those duplicates must be consumed.
    """
    args = seq[2:] if seq[0] == 0xFC else seq[1:]
    glyphs: List[str] = []
    for byte in args:
        ch = TextDecoder.POKEMON_DECODE.get(byte)
        if not ch or len(ch) != 1 or ch.isspace():
            break
        glyphs.append(ch)
    return glyphs


def _skip_argument_glyphs(text: str, index: int, expected: List[str]) -> int:
    """Consume the decoded argument glyphs duplicated after a placeholder.

    Skips a character only when it matches the glyph the argument byte
    decodes to (accent-insensitively). A blind fixed-count skip ate the
    first letter of the following word ("sentir" became "entir").
    """
    for glyph in expected:
        if index >= len(text):
            break
        ch = text[index]
        if ch != glyph and _strip_accents(ch) != _strip_accents(glyph):
            break
        index += 1
    return index


def _replace_placeholders(text: str, sequences: List[List[int]]) -> str:
    if not sequences:
        return text
    result: List[str] = []
    i = 0
    while i < len(text):
        if text[i] == '{':
            end = text.find('}', i + 1)
            if end != -1:
                token = text[i:end + 1]
                if token == '{COLOR}':
                    result.append(token)
                    i = end + 1
                    continue
                if sequences:
                    seq = sequences.pop(0)
                    result.append(_format_sequence(seq))
                    i = end + 1
                    if seq[0] in ARG_CONSUME_PREFIXES and len(seq) > 1:
                        i = _skip_argument_glyphs(text, i, _argument_glyphs(seq))
                    continue
        result.append(text[i])
        i += 1
    return ''.join(result)


def _apply_control_placeholders(
    translation: str,
    english_text: Optional[str],
    english_raw_bytes: Optional[str] = None,
) -> str:
    if not translation or not english_text:
        return translation
    if '{' not in translation:
        return translation
    color_sequences, other_sequences = _extract_control_sequences(
        english_text,
        english_raw_bytes,
    )
    if not color_sequences and not other_sequences:
        return translation

    def repl_color(match: re.Match) -> str:
        if color_sequences:
            return _format_sequence(color_sequences.pop(0))
        return match.group(0)

    if '{COLOR}' in translation:
        translation = COLOR_MARKER_RE.sub(repl_color, translation)
        translation = re.sub(r'\{COLOR\}', repl_color, translation)

    return _replace_placeholders(translation, other_sequences)


def _read_raw_entry(
    rom_data: bytes,
    offset: int,
    encoding: str,
    max_length: int = 2000,
) -> Optional[dict]:
    if offset < 0 or offset >= len(rom_data):
        return None
    terminator = 0x00 if encoding == 'ascii' else 0xFF
    end = min(len(rom_data), offset + max_length)
    chunk = rom_data[offset:end]
    idx = chunk.find(bytes([terminator]))
    if idx == -1:
        return None
    raw = bytes(chunk[: idx + 1])
    if encoding == 'ascii':
        decoded = TextDecoder.decode_ascii(raw, preserve_unknown=True)
    else:
        decoded = TextDecoder.decode_pokemon(raw, preserve_unknown=True)
    return {
        'offset': offset,
        'byte_length': len(raw),
        'length': len(raw),
        'encoding': encoding,
        'raw_bytes': raw.hex(),
        'text': decoded,
        'decoded_text': decoded,
    }


def _apply_translation_at_offset(
    rom_data: bytearray,
    offset: int,
    translation: str,
    reference_entry: dict,
    detector: PaddingDetector,
) -> Tuple[bool, str]:
    encoding = reference_entry.get('encoding', 'pokemon')
    encoded = TextEncoder.encode(translation, encoding)
    encoded_len = max(len(encoded) - 1, 0)
    reference_length = max(reference_entry.get('byte_length', 0) - 1, 0)
    padding = detector.detect_padding(offset, reference_length, extended_search=True)
    max_length = reference_length + padding

    if encoded_len > max_length:
        return False, 'too_long'
    end = offset + len(encoded)
    if end > len(rom_data):
        return False, 'missing'

    rom_data[offset:end] = encoded
    return True, 'applied'


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Apply inline French overrides using Spanish inline diffs.'
    )
    parser.add_argument('--rom', type=Path, required=True, help='Built French ROM to patch')
    parser.add_argument('--source', type=Path, required=True, help='English ROM (source)')
    parser.add_argument('--combined', type=Path, required=True, help='combined_fr.txt')
    parser.add_argument(
        '--reference-texts',
        type=Path,
        default=Path('output/extracted/extracted_texts/spanishrom_texts.json'),
        help='Spanish extracted JSON',
    )
    parser.add_argument(
        '--english-texts',
        type=Path,
        default=Path('output/extracted/extracted_texts/englishrom_texts.json'),
        help='English extracted JSON (placeholder mapping)',
    )
    parser.add_argument(
        '--translations',
        type=Path,
        help='Translation JSON to skip pointer-based offsets',
    )
    parser.add_argument('--min-length', type=int, default=12, help='Min inline length')

    args = parser.parse_args()

    for path in (args.rom, args.source, args.combined):
        if not path.exists():
            print(f'Error: missing file: {path}')
            return 1

    combined_map, skipped = _load_combined(args.combined)
    if not combined_map:
        print('No combined entries found.')
        return 1

    translated_offsets = _load_translation_offsets(args.translations)
    translation_items = _load_translation_items(args.translations)
    template_map = _build_template_map(translation_items)
    spanish_map = _load_extracted_map(args.reference_texts)
    english_map = _load_extracted_map(args.english_texts)

    if not spanish_map:
        print(f'Error: missing Spanish extracted JSON: {args.reference_texts}')
        return 1

    source_reader = ROMReader(str(args.source))
    source_reader.load()
    source_data = source_reader.rom_data
    detector = PaddingDetector(source_reader)

    rom_data = bytearray(args.rom.read_bytes())
    categorizer = JSONToCSVConverter()
    applied_combined = 0
    applied_templates = 0
    skipped_not_inline = 0
    skipped_missing = 0
    skipped_too_long = 0
    skipped_empty = 0
    skipped_template_no_match = 0
    skipped_fixed_table = 0

    for offset, translation in combined_map.items():
        if in_fixed_table(offset):
            # Fixed-stride name tables are already French in the source
            # ROM; rewriting them breaks cell alignment and terminators.
            skipped_fixed_table += 1
            continue
        if translated_offsets and offset in translated_offsets:
            continue
        ref_entry = spanish_map.get(offset)
        if not ref_entry:
            skipped_missing += 1
            continue

        if not translation:
            skipped_empty += 1
            continue

        english_entry = english_map.get(offset)
        if not english_entry:
            encoding_hint = ref_entry.get('encoding', 'pokemon')
            tried = set()
            for enc in (encoding_hint, 'pokemon', 'ascii'):
                if enc in tried:
                    continue
                tried.add(enc)
                english_entry = _read_raw_entry(source_data, offset, enc)
                if english_entry:
                    break

        # The Spanish extraction can be misaligned at an offset (junk short
        # entry) while the English ROM holds a real string there: accept the
        # candidate when either side reaches the minimum inline length.
        english_length = (english_entry or {}).get('byte_length', 0)
        if max(ref_entry.get('byte_length', 0), english_length) < args.min_length:
            skipped_not_inline += 1
            continue

        reference_entry = english_entry or ref_entry
        reference_text = reference_entry.get('decoded_text') or reference_entry.get('text')
        reference_raw = reference_entry.get('raw_bytes')

        translation = _apply_control_placeholders(
            translation,
            reference_text,
            reference_raw,
        )

        # Re-balance dialogue line breaks against the FRLG font metrics
        # (and enforce the Gen III \n / scroll rule).
        if (
            reference_entry.get('encoding', 'pokemon') == 'pokemon'
            and categorizer.categorize_text(reference_text or '', offset) == 'dialogue'
        ):
            try:
                translation = rewrap_dialogue(translation)
            except Exception:
                pass

        applied, reason = _apply_translation_at_offset(
            rom_data,
            offset,
            translation,
            reference_entry,
            detector,
        )
        if applied:
            applied_combined += 1
        elif reason == 'too_long':
            skipped_too_long += 1
        elif reason == 'missing':
            skipped_missing += 1

    combined_offsets = set(combined_map.keys())
    fallback_offsets = [
        offset for offset, entry in english_map.items()
        if offset not in translated_offsets
        and offset not in combined_offsets
        and (entry.get('pointer_offsets') or entry.get('table_offsets'))
    ]

    for offset in fallback_offsets:
        if in_fixed_table(offset):
            skipped_fixed_table += 1
            continue
        english_entry = english_map.get(offset)
        if not english_entry:
            continue
        english_text = english_entry.get('decoded_text') or english_entry.get('text')
        if not english_text:
            continue

        key, groups = _group_dynamic_tokens(english_text)
        if not groups:
            skipped_template_no_match += 1
            continue
        template = template_map.get(key)
        if not template:
            skipped_template_no_match += 1
            continue
        if template.count(GROUP_PLACEHOLDER) != len(groups):
            skipped_template_no_match += 1
            continue

        translation = template
        for group in groups:
            translation = translation.replace(GROUP_PLACEHOLDER, group, 1)
        translation = _apply_control_placeholders(
            translation,
            english_text,
            english_entry.get('raw_bytes'),
        )
        if translation == english_text:
            skipped_template_no_match += 1
            continue

        applied, reason = _apply_translation_at_offset(
            rom_data,
            offset,
            translation,
            english_entry,
            detector,
        )
        if applied:
            applied_templates += 1
        elif reason == 'too_long':
            skipped_too_long += 1
        elif reason == 'missing':
            skipped_missing += 1

    args.rom.write_bytes(rom_data)

    print(f'Combined entries: {len(combined_map)} (skipped lines: {skipped})')
    print(f'Inline overrides applied (combined): {applied_combined}')
    print(f'Template overrides applied: {applied_templates}')
    print(f'Skipped (not inline): {skipped_not_inline}')
    print(f'Skipped (missing): {skipped_missing}')
    print(f'Skipped (too long): {skipped_too_long}')
    print(f'Skipped (empty): {skipped_empty}')
    print(f'Skipped (template miss): {skipped_template_no_match}')
    print(f'Skipped (fixed table): {skipped_fixed_table}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
