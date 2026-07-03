#!/usr/bin/env python3
"""Bucket the Italian "phantom" (no-live-pointer) offsets by ROM region and
report, per bucket, whether a dedicated patch actually writes Italian text
there.

Follow-up to B-162 / the debug/pipeline investigation: ``combined_it.txt``
authors ~15k offsets, but only ~11k reach ``it_translation_ready.json`` — the
rest have no 32-bit pointer in ``englishrom.gba`` (fixed-table cells reached
by index arithmetic) and are the domain of the dedicated
``languages/it/patches/*.py`` scripts, not the generic CSV/JSON pipeline.

This script does NOT re-implement pointer tracing (that's
``scripts/audit_translation_collisions.py``, which already classifies every
``combined_it.txt`` offset as phantom/collision/ok). It consumes that
classification, groups the phantom offsets into coarse ROM regions, and
diffs the built ROM against the English source at each offset as a cheap
"did *anything* touch this cell" signal.

Usage::

    python3 scripts/build_language.py it --build-number 999   # produce the ROM
    python3 scripts/audit_translation_collisions.py \\
        --combined languages/it/combined_it.txt \\
        --rom output/roms/GenedRom-it.gba \\
        --english input/roms/englishrom.gba \\
        --json /tmp/it_phantom_audit.json
    python3 scripts/audit_it_table_offset_coverage.py /tmp/it_phantom_audit.json

Caveat: a cell reading "unchanged" is NOT proof of a gap by itself — some
tables (Pokédex descriptions, notably) get their live text via a struct
pointer that the generic builder may relocate elsewhere, leaving the
original combined_it.txt-authored offset untouched even though the game
displays the translated text correctly. Byte-diff is a triage signal, not a
verdict; see docs/it-table-offset-coverage.md for the per-bucket verdicts
this script's output was cross-checked against (patch source review +
targeted live-pointer sampling).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Coarse region -> human label, used only to make the printed table readable.
# Boundaries come from sampling combined_it.txt text at cluster edges (see
# docs/it-table-offset-coverage.md for the worked examples).
REGIONS = [
    (0x0230000, 0x0240000, "trainer class names (13B no-ptr table)"),
    (0x03D0000, 0x03E0000, "item descriptions (general, Poke Ball/Berry/Spray text)"),
    (0x03F0000, 0x0400000, "battle status control-code strings"),
    (0x0410000, 0x0420000, "battle/menu UI strings"),
    (0x0480000, 0x0490000, "move descriptions (duplicate/legacy table copy)"),
    (0x0870000, 0x0880000, "item name table (gItems, 44B stride)"),
    (0x0A30000, 0x0A37D00, "ability names (17B fixed table)"),
    (0x0A37D00, 0x0A40000, "ability descriptions (no dedicated table found)"),
    (0x0A40000, 0x0A50000, "move names (no dedicated table found)"),
    (0x1660000, 0x1670000, "Pokedex flavour text"),
    (0x1F40000, 0x1FA0000, "long dialogues / over-cap main-text cells"),
]


def bucket_label(offset: int) -> str:
    for lo, hi, label in REGIONS:
        if lo <= offset < hi:
            return label
    return f"unclassified (0x{offset:06X})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_json", type=Path, help="output of audit_translation_collisions.py --json")
    parser.add_argument("--rom", type=Path, default=REPO_ROOT / "output/roms/GenedRom-it.gba")
    parser.add_argument("--english", type=Path, default=REPO_ROOT / "input/roms/englishrom.gba")
    parser.add_argument("--cmp-len", type=int, default=24, help="bytes compared EN vs built ROM per offset")
    args = parser.parse_args()

    report = json.loads(args.audit_json.read_text())
    phantom = sorted(int(o, 16) for o in report["phantom"])

    en = args.english.read_bytes() if args.english.exists() else None
    rom = args.rom.read_bytes() if args.rom.exists() else None

    counts = Counter()
    unchanged = Counter()
    for offset in phantom:
        label = bucket_label(offset)
        counts[label] += 1
        if en is not None and rom is not None:
            if en[offset:offset + args.cmp_len] == rom[offset:offset + args.cmp_len]:
                unchanged[label] += 1

    print(f"Phantom offsets audited: {len(phantom)}")
    print()
    print(f"{'bucket':<55} {'count':>6} {'unchanged*':>10}")
    for label, total in counts.most_common():
        print(f"{label:<55} {total:>6} {unchanged.get(label, 0):>10}")
    print()
    print("* unchanged = raw bytes identical to englishrom.gba at that offset.")
    print("  A cheap triage signal, NOT a verdict — see docs/it-table-offset-coverage.md")
    print("  for the per-bucket coverage verdicts (patch source review required for")
    print("  tables whose live text is reached via a relocatable struct pointer).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
