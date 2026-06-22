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
import bisect
import json
import struct
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

GBA_BASE = 0x08000000

# Event-script bytecode whose bytes coincidentally read as a valid text
# pointer must never be repointed: the pointer scan that feeds this pass
# cannot tell a real pointer from a `setflag`/operand run that happens to
# equal a string's GBA address. These windows live inside legendary-ritual
# scripts (Ho-Oh/Lugia and Groudon/Red-Orb) and read as 0x09F62908 ("I swam,
# of course!"); rewriting them breaks the cutscene so the legendary battle
# never launches. See scripts/patch_legendary_ritual_fr.py for the full
# diagnosis.
PROTECTED_SCRIPT_OFFSETS: frozenset[int] = frozenset(
    {0x1E8C677, 0x1E8C782, 0x1E59D1F}
)

# CFRU `setflag` opcode. A "stale pointer" whose bytes are really the operand
# tail of a `setflag X / setflag Y` chain is script bytecode, not a pointer
# slot, and must never be repointed.
SETFLAG_OPCODE = 0x29


def _is_setflag_chain(rom: bytearray, loc: int) -> bool:
    """True if the 4-byte window at ``loc`` is the operand tail of a
    ``setflag X / setflag Y`` chain: byte two-before is the 0x29 ``setflag``
    opcode and the window's second byte is another ``setflag`` opcode (the run
    ``29 XX <op> 29 YY ZZ`` the repointer false-matches). A genuine relocated
    text pointer never has this shape."""
    if loc < 2 or loc + 4 > len(rom):
        return False
    return rom[loc - 2] == SETFLAG_OPCODE and rom[loc + 1] == SETFLAG_OPCODE


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


def _entry_byte_length(entry: dict) -> int:
    length = entry.get('byte_length')
    if isinstance(length, int) and length > 0:
        return length
    raw_hex = entry.get('raw_bytes') or ''
    return max(len(raw_hex) // 2, 1)


def _translated_spans(
    texts: list[dict],
    translated_offsets: set[int],
) -> tuple[list[tuple[int, int]], list[int]]:
    spans = []
    for entry in texts:
        offset = entry.get('offset')
        if isinstance(offset, int) and offset in translated_offsets:
            spans.append((offset, offset + _entry_byte_length(entry)))
    spans.sort()
    return spans, [start for start, _ in spans]


def repoint(
    rom: bytearray,
    texts: list[dict],
    translated_offsets: set[int],
) -> int:
    fixed = 0
    rom_size = len(rom)

    # The pointer scan records every 4-byte window that decodes to a ROM
    # address — including plain text (the '<terminator><FC><01><08>' run
    # at a string boundary reads as a pointer to 0x1FCFF). Writing such a
    # location corrupts the translation, so any window overlapping a
    # translated string's bytes is vetoed.
    spans, span_starts = _translated_spans(texts, translated_offsets)

    def in_translated_text(loc: int) -> bool:
        i = bisect.bisect_right(span_starts, loc + 3) - 1
        for j in range(max(0, i - 1), min(len(spans), i + 2)):
            start, end = spans[j]
            if loc < end and loc + 4 > start:
                return True
        return False

    for entry in texts:
        locations = _parse_pointer_locations(entry)
        if len(locations) < 2:
            continue
        offset = entry.get('offset')
        if not isinstance(offset, int):
            continue
        # Only the builder relocates strings, and it only relocates
        # translated ones. Any other extraction entry whose "pointers"
        # diverge is a junk pattern match, not a relocated string.
        if offset not in translated_offsets:
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
            if in_translated_text(loc):
                continue
            if loc in PROTECTED_SCRIPT_OFFSETS:
                # Script bytecode masquerading as a text pointer — leave it.
                continue
            if _is_setflag_chain(rom, loc):
                # General guard: the stale "pointer" is the operand tail of a
                # `setflag X / setflag Y` chain (0x29 opcode both two-before and
                # at the window's second byte), not a real pointer slot. Writing
                # it mangles the script. This catches every site with the
                # Ho-Oh/Lugia/Groudon signature without an explicit allow-list.
                continue
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
    parser.add_argument(
        '--translations',
        type=Path,
        required=True,
        help='Translation JSON (only these strings can have been relocated)',
    )
    args = parser.parse_args()

    for path in (args.target, args.english_texts, args.translations):
        if not path.exists():
            raise SystemExit(f'Missing file: {path}')

    data = json.loads(args.english_texts.read_text(encoding='utf-8'))
    translations = json.loads(args.translations.read_text(encoding='utf-8'))
    translated_offsets = {
        item['offset']
        for item in translations.get('translations', [])
        if isinstance(item.get('offset'), int)
    }
    rom = bytearray(args.target.read_bytes())
    fixed = repoint(rom, data.get('texts', []), translated_offsets)
    args.target.write_bytes(rom)
    print(f'Stale pointers re-targeted: {fixed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
