#!/usr/bin/env python3
"""
Compare pointer-based extracted texts between two ROMs.

Produces:
- diff report (modified / only_in_english / only_in_spanish)
- translation dataset containing EN/ES pairs with raw bytes and decoded text
- offset map (matched or unmatched)
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple


def _load_texts(path: Path) -> Tuple[Dict[int, Dict], Dict]:
    with path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)
    texts = {}
    for item in data.get('texts', []):
        offset = item.get('offset')
        if offset is None:
            continue
        texts[int(offset)] = item
    return texts, data


def _build_entry(entry: Dict) -> Dict:
    return {
        'offset': entry.get('offset'),
        'encoding': entry.get('encoding'),
        'byte_length': entry.get('byte_length', entry.get('length')),
        'raw_bytes': entry.get('raw_bytes'),
        'decoded_text': entry.get('decoded_text', entry.get('text')),
    }


def compare(english_path: Path, spanish_path: Path) -> Dict:
    en_texts, en_meta = _load_texts(english_path)
    es_texts, es_meta = _load_texts(spanish_path)

    en_offsets = set(en_texts.keys())
    es_offsets = set(es_texts.keys())

    only_en = sorted(en_offsets - es_offsets)
    only_es = sorted(es_offsets - en_offsets)
    common = sorted(en_offsets & es_offsets)

    diffs: List[Dict] = []
    translation_pairs: List[Dict] = []
    offset_map: List[Dict] = []

    for offset in common:
        en_entry = en_texts[offset]
        es_entry = es_texts[offset]

        en_raw = en_entry.get('raw_bytes')
        es_raw = es_entry.get('raw_bytes')
        en_text = en_entry.get('decoded_text', en_entry.get('text'))
        es_text = es_entry.get('decoded_text', es_entry.get('text'))

        modified = (en_raw != es_raw) or (en_text != es_text)
        if modified:
            diffs.append({
                'offset': offset,
                'type': 'modified',
                'english': _build_entry(en_entry),
                'spanish': _build_entry(es_entry),
            })

        translation_pairs.append({
            'offset': offset,
            'english': _build_entry(en_entry),
            'spanish': _build_entry(es_entry),
            'modified': modified,
        })

        offset_map.append({
            'english_offset': offset,
            'spanish_offset': offset,
            'status': 'matched',
        })

    for offset in only_en:
        diffs.append({
            'offset': offset,
            'type': 'only_in_english',
            'english': _build_entry(en_texts[offset]),
        })
        offset_map.append({
            'english_offset': offset,
            'spanish_offset': None,
            'status': 'only_in_english',
        })

    for offset in only_es:
        diffs.append({
            'offset': offset,
            'type': 'only_in_spanish',
            'spanish': _build_entry(es_texts[offset]),
        })
        offset_map.append({
            'english_offset': None,
            'spanish_offset': offset,
            'status': 'only_in_spanish',
        })

    report = {
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'english_source': str(english_path),
        'spanish_source': str(spanish_path),
        'english_texts': en_meta.get('text_count', len(en_texts)),
        'spanish_texts': es_meta.get('text_count', len(es_texts)),
        'counts': {
            'common': len(common),
            'only_in_english': len(only_en),
            'only_in_spanish': len(only_es),
            'modified': len([d for d in diffs if d['type'] == 'modified']),
        },
        'diffs': diffs,
        'offset_map': offset_map,
        'translation_pairs': translation_pairs,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description='Pointer-based diff for extracted texts')
    parser.add_argument('--english', required=True, help='English extraction JSON')
    parser.add_argument('--spanish', required=True, help='Spanish extraction JSON')
    parser.add_argument('--diff-out', required=True, help='Diff report JSON output')
    parser.add_argument('--pairs-out', required=True, help='Translation pairs JSON output')
    parser.add_argument('--map-out', required=True, help='Offset map JSON output')

    args = parser.parse_args()

    report = compare(Path(args.english), Path(args.spanish))

    diff_out = Path(args.diff_out)
    diff_out.parent.mkdir(parents=True, exist_ok=True)
    with diff_out.open('w', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    pairs_out = Path(args.pairs_out)
    pairs_out.parent.mkdir(parents=True, exist_ok=True)
    with pairs_out.open('w', encoding='utf-8') as handle:
        json.dump({'translation_pairs': report['translation_pairs']}, handle, indent=2, ensure_ascii=False)

    map_out = Path(args.map_out)
    map_out.parent.mkdir(parents=True, exist_ok=True)
    with map_out.open('w', encoding='utf-8') as handle:
        json.dump({'offset_map': report['offset_map']}, handle, indent=2, ensure_ascii=False)

    print(f"Diff report: {diff_out}")
    print(f"Translation pairs: {pairs_out}")
    print(f"Offset map: {map_out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
