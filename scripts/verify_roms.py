#!/usr/bin/env python3
"""
Verify input ROMs against a baseline file.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def _load_baseline(path: Path) -> Dict:
    with path.open('r', encoding='ascii') as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify ROM checksums and sizes')
    parser.add_argument(
        '--baseline',
        default='docs/roms_baseline.json',
        help='Path to baseline JSON (default: docs/roms_baseline.json)'
    )
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    if not baseline_path.exists():
        print(f"ERROR: baseline file not found: {baseline_path}")
        return 2

    data = _load_baseline(baseline_path)
    roms = data.get('roms', {})
    if not roms:
        print(f"ERROR: no roms found in baseline: {baseline_path}")
        return 2

    failures = 0
    for rom_name, info in roms.items():
        path = Path(info.get('path', ''))
        expected_size = info.get('size_bytes')
        expected_hash = info.get('sha256')

        if not path.exists():
            print(f"ERROR: {rom_name} missing: {path}")
            failures += 1
            continue

        actual_size = path.stat().st_size
        if actual_size != expected_size:
            print(
                f"ERROR: {rom_name} size mismatch: "
                f"expected {expected_size}, got {actual_size}"
            )
            failures += 1

        actual_hash = _sha256_file(path)
        if actual_hash != expected_hash:
            print(
                f"ERROR: {rom_name} sha256 mismatch: "
                f"expected {expected_hash}, got {actual_hash}"
            )
            failures += 1

    if failures:
        print(f"FAIL: {failures} rom(s) do not match baseline")
        return 1

    print("OK: input roms match baseline")
    return 0


if __name__ == '__main__':
    sys.exit(main())
