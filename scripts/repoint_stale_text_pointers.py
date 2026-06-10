#!/usr/bin/env python3
"""Re-target text pointers clobbered by the LZ77 repair passes.

The builder relocates over-long translations to free space and updates
every known pointer. The LZ77 repair passes then restore "stable"
blocks from the English ROM — and some of those blocks are false
positives (script bytecode that happens to decompress), so a freshly
updated pointer inside them reverts to the English string.

This pass runs after the repairs. For every extracted string whose
pointers diverge — at least one pointer already re-targeted to a single
relocated copy, while others still hold the original English address
(whose bytes are untouched English text) — it re-writes the stale
pointers to the relocated copy.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

GBA_BASE = 0x08000000


def _parse_pointer_locations(entry: dict) -> list[int]:
    locations = []
    for value in entry.get('pointer_offsets') or []:
        if isinstance(value, int):
            locations.append(value)
        elif isinstance(value, str):
            try:
                locations.append(int(value, 16))
            except ValueError:
                continue
    return locations


def repoint(rom: bytearray, texts: list[dict]) -> int:
    fixed = 0
    rom_size = len(rom)
    for entry in texts:
        locations = _parse_pointer_locations(entry)
        if len(locations) < 2:
            continue
        offset = entry.get('offset')
        if not isinstance(offset, int):
            continue
        original_value = GBA_BASE + offset
        values = []
        for loc in locations:
            if loc < 0 or loc + 4 > rom_size:
                values.append(None)
                continue
            values.append(struct.unpack_from('<I', rom, loc)[0])

        new_targets = {
            v for v in values
            if v is not None and v != original_value
            and GBA_BASE <= v < GBA_BASE + rom_size
        }
        if len(new_targets) != 1:
            continue
        stale = [
            loc for loc, v in zip(locations, values) if v == original_value
        ]
        if not stale:
            continue

        # Only re-target when the original location still holds the
        # untouched English bytes (i.e. the string was relocated, not
        # translated in place).
        raw_hex = entry.get('raw_bytes')
        if raw_hex:
            raw = bytes.fromhex(raw_hex)
            if rom[offset:offset + len(raw)] != raw:
                continue

        target = new_targets.pop()
        # The relocated copy must be a plausible terminated string.
        target_offset = target - GBA_BASE
        terminator = rom.find(b'\xff', target_offset, target_offset + 0x800)
        if terminator == -1:
            continue

        for loc in stale:
            struct.pack_into('<I', rom, loc, target)
            fixed += 1
    return fixed


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Re-target text pointers reverted by LZ77 repairs.'
    )
    parser.add_argument('--target', type=Path, required=True, help='ROM to patch')
    parser.add_argument(
        '--english-texts',
        type=Path,
        default=Path('output/extracted/extracted_texts/englishrom_texts.json'),
        help='English extraction JSON (pointer locations)',
    )
    args = parser.parse_args()

    for path in (args.target, args.english_texts):
        if not path.exists():
            raise SystemExit(f'Missing file: {path}')

    data = json.loads(args.english_texts.read_text(encoding='utf-8'))
    rom = bytearray(args.target.read_bytes())
    fixed = repoint(rom, data.get('texts', []))
    args.target.write_bytes(rom)
    print(f'Stale pointers re-targeted: {fixed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
