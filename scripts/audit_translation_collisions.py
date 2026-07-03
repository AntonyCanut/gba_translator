#!/usr/bin/env python3
"""Audit a built translated ROM for inter-cell text collisions and phantom cells.

Language-agnostic: point it at any ``combined_<code>.txt`` and its built ROM to
verify no translated string overruns its terminator into the next live cell —
the fusion / freeze failure mode described in ``src/core/collision_check.py``.

It reports three classes of offset:

* **phantom**   — no plausible pointer in the English ROM addresses this cell;
  the scanner captured it but the game never reads it through a pointer.
* **collision** — a cell read in place (or a phantom) whose string is *not*
  terminated by ``0xFF`` before the next occupied offset: it fuses with / writes
  over its neighbour. These are the dangerous ones.
* **ok**        — terminated in place, or safely relocated + repointed.

Usage::

    python3 scripts/audit_translation_collisions.py \
        --combined languages/de/combined_de.txt \
        --rom output/roms/GenedRom-de.gba \
        --english input/roms/englishrom.gba \
        [--region 0x920000-0xA40000] [--json report.json] [--fail-on-collision]

With ``--english`` the audit distinguishes phantom from relocated cells and
traces live pointers; without it, it falls back to a pure terminator-vs-next
scan over every offset.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.collision_check import (  # noqa: E402
    build_pointer_index,
    find_collisions,
    has_live_pointer,
)

LINE_RE = re.compile(r'^\s*0x([0-9A-Fa-f]+)\s*:')


def load_offsets(combined: Path) -> list:
    offsets = []
    with combined.open(encoding='utf-8') as f:
        for line in f:
            m = LINE_RE.match(line)
            if m:
                offsets.append(int(m.group(1), 16))
    # Dedup preserving the "last wins" semantics does not matter for offsets;
    # a set is enough since we only need the occupied positions.
    return sorted(set(offsets))


def parse_region(text: str) -> tuple:
    lo, _, hi = text.partition('-')
    return (int(lo, 16), int(hi, 16))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--combined', type=Path, required=True,
                        help='combined_<code>.txt whose offsets to audit')
    parser.add_argument('--rom', type=Path, required=True,
                        help='built translated ROM to inspect')
    parser.add_argument('--english', type=Path, default=None,
                        help='English source ROM (enables pointer tracing / phantom detection)')
    parser.add_argument('--region', type=parse_region, default=None,
                        help='hex range LO-HI to restrict the audit (e.g. 0x920000-0xA40000)')
    parser.add_argument('--json', type=Path, default=None, help='write a JSON report here')
    parser.add_argument('--fail-on-collision', action='store_true',
                        help='exit non-zero when any collision is found')
    parser.add_argument('--show', type=int, default=25, help='max collisions to print')
    args = parser.parse_args()

    for path in (args.combined, args.rom):
        if not path.exists():
            print(f"❌ Not found: {path}", file=sys.stderr)
            return 2

    offsets = load_offsets(args.combined)
    built = args.rom.read_bytes()

    en_rom = None
    en_index = None
    if args.english and args.english.exists():
        en_rom = args.english.read_bytes()
        print(f"⏳ Indexing pointers in {args.english.name} …")
        en_index = build_pointer_index(en_rom)

    region = args.region
    lo, hi = region if region else (None, None)

    phantom = []
    if en_index is not None:
        for off in offsets:
            if region and not (lo <= off < hi):
                continue
            if not has_live_pointer(en_index, off, en_rom=en_rom, require_plausible=True):
                phantom.append(off)

    collisions = find_collisions(
        built, offsets, en_index=en_index, en_rom=en_rom, source_rom=en_rom,
        region=region,
    )

    # With a source ROM every reported collision is confirmed: the English
    # source had a cell boundary here that the build destroyed. The neighbour
    # being live-pointed too (`next_is_live`) is extra corroboration.
    confirmed = collisions  # source_rom gate already applied in find_collisions
    live_neighbour = [c for c in confirmed if c.extra.get('next_is_live', True)]

    audited = [o for o in offsets if not region or (lo <= o < hi)]
    print("=" * 70)
    print(f"Collision audit — {args.combined.name} vs {args.rom.name}")
    print("=" * 70)
    print(f"  Offsets audited:    {len(audited)}"
          + (f"  (region 0x{lo:X}-0x{hi:X})" if region else ""))
    if en_index is not None:
        print(f"  Phantom cells:      {len(phantom)}  (no plausible live pointer)")
    if en_rom is not None:
        print(f"  Collisions:         {len(confirmed)}  (build destroyed an English cell boundary)")
        print(f"    └─ live neighbour:  {len(live_neighbour)}  (fuses a still-pointed cell)")
    else:
        print(f"  Collisions:         {len(confirmed)}  (overrun; no source ROM → unconfirmed)")

    if confirmed:
        print("\n  ⚠ COLLISIONS (translated string not terminated before next cell):")
        for c in sorted(confirmed, key=lambda c: -c.extra.get('gap_bytes', 0))[:args.show]:
            print(f"    0x{c.offset:X} → next 0x{c.next_offset:X} [{c.kind}] "
                  f"gap={c.extra.get('gap_bytes')}: {c.decoded[:80]!r}")
        if len(confirmed) > args.show:
            print(f"    … and {len(confirmed) - args.show} more")

    if args.json:
        args.json.write_text(json.dumps({
            'combined': str(args.combined),
            'rom': str(args.rom),
            'region': [f"0x{lo:X}", f"0x{hi:X}"] if region else None,
            'audited': len(audited),
            'phantom_count': len(phantom),
            'phantom': [f"0x{o:X}" for o in phantom],
            'collision_count': len(confirmed),
            'live_neighbour_count': len(live_neighbour),
            'collisions': [c.as_dict() for c in confirmed],
        }, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"\n✅ JSON report: {args.json}")

    if confirmed and args.fail_on_collision:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
