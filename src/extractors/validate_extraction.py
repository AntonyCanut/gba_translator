#!/usr/bin/env python3
"""
Validate extracted text JSON for duplicates and invalid lengths.
"""

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List


def validate(data: Dict, max_length: int) -> Dict:
    texts: List[Dict] = data.get('texts', [])
    seen_offsets = set()
    duplicates = []
    invalid_lengths = []

    for entry in texts:
        offset = entry.get('offset')
        length = entry.get('byte_length', entry.get('length'))
        if offset in seen_offsets:
            duplicates.append(offset)
        else:
            seen_offsets.add(offset)

        if length is None or length < 1 or length > max_length:
            invalid_lengths.append({'offset': offset, 'length': length})

    return {
        'generated_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'text_count': len(texts),
        'duplicates': duplicates,
        'invalid_lengths': invalid_lengths,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate extracted text JSON')
    parser.add_argument('input', help='Extraction JSON path')
    parser.add_argument('--max-length', type=int, default=1000, help='Max text length')
    parser.add_argument('--report', help='Optional JSON report output')
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input not found: {input_path}")
        return 2

    with input_path.open('r', encoding='utf-8') as handle:
        data = json.load(handle)

    report = validate(data, args.max_length)

    dup_count = len(report['duplicates'])
    bad_count = len(report['invalid_lengths'])
    print(f"Texts: {report['text_count']}")
    print(f"Duplicates: {dup_count}")
    print(f"Invalid lengths: {bad_count}")

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open('w', encoding='utf-8') as handle:
            json.dump(report, handle, indent=2)
        print(f"Report written: {report_path}")

    if dup_count or bad_count:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
