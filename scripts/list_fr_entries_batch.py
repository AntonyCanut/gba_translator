#!/usr/bin/env python3
"""List a deterministic batch slice of languages/fr/combined_fr.txt for translation.

Deduplicates by offset (last occurrence in the file wins, matching the FR
build chain semantics), sorts the unique offsets ascending, then slices that
sorted list into fixed-size batches. Batch numbering is 1-based.

Used to hand out the German (or any future language) translation work in
reproducible, non-overlapping chunks across a chain of tickets — the batch
boundaries only depend on combined_fr.txt content, not on run order.

Usage:
    python3 scripts/list_fr_entries_batch.py <batch_number> [--size 2000] \
        [--skip-existing languages/de/combined_de.txt]
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LINE_RE = re.compile(r'^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$')


def load_entries(path: Path) -> dict[int, str]:
    entries: dict[int, str] = {}
    with path.open(encoding='utf-8') as f:
        for line in f:
            m = LINE_RE.match(line)
            if not m:
                continue
            entries[int(m.group(1), 16)] = m.group(2)
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('batch', type=int, help='1-based batch number')
    parser.add_argument('--size', type=int, default=2000, help='entries per batch')
    parser.add_argument(
        '--fr', type=Path, default=REPO_ROOT / 'languages/fr/combined_fr.txt'
    )
    parser.add_argument(
        '--skip-existing', type=Path, default=None,
        help='a combined_<code>.txt whose offsets should be excluded (already translated)',
    )
    args = parser.parse_args()

    fr_entries = load_entries(args.fr)
    offsets = sorted(fr_entries)

    if args.skip_existing and args.skip_existing.exists():
        done = load_entries(args.skip_existing)
        offsets = [o for o in offsets if o not in done]

    total_batches = (len(offsets) + args.size - 1) // args.size
    start = (args.batch - 1) * args.size
    end = start + args.size
    slice_offsets = offsets[start:end]

    print(f'# batch {args.batch}/{total_batches} — {len(slice_offsets)} entries '
          f'(of {len(offsets)} remaining, {len(fr_entries)} total unique offsets)')
    for off in slice_offsets:
        print(f'0x{off:X}: {fr_entries[off]}')


if __name__ == '__main__':
    main()
