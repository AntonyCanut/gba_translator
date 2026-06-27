#!/usr/bin/env python3
"""
Cross-language translation coverage audit for Pokémon Unbound.

Goal
----
Answer the question: *"For every text pointer (offset), what do I have in
English, French, Italian, Spanish … and where are the holes I still need to
fill on the new languages?"*

English (``languages/en/combined_en.txt``) is the **reference**: it is an
extraction of the source ROM at every offset present in the French master
file, so its key set is the universe of translatable strings. Each other
language's ``combined_<code>.txt`` is compared against it.

For every language the script reports:

  * ``present``        offsets that have an entry in that language's file
  * ``missing``        offsets in EN but absent from the language → stay English
  * ``untranslated``   offsets present but whose text is byte-identical to EN
                       (copied through, not actually translated)
  * ``translated``     present AND different from EN (real translation)
  * ``orphan``         offsets in the language but NOT in the EN reference

German (``de``) is excluded by default per the audit request; pass
``--include-de`` to add it.

Outputs
-------
1. A human-readable summary table on stdout.
2. ``output/audit/translation_coverage.csv`` — one row per offset with the EN
   source text and every audited language's text plus a ``status`` column,
   so the holes can be filled offset by offset.
3. ``output/audit/translation_gaps_<code>.csv`` — per target language, only the
   rows that still need work (missing + untranslated), EN text alongside, ready
   to hand to a translator.

Usage::

    python3 scripts/audit_translation_coverage.py
    python3 scripts/audit_translation_coverage.py --include-de
    python3 scripts/audit_translation_coverage.py --languages it,es
"""

from __future__ import annotations

import argparse
import collections
import csv
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LANGUAGES_DIR = REPO_ROOT / "languages"

LINE_RE = re.compile(r"^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$")

# Order in which languages appear in the wide CSV / summary.
DEFAULT_ORDER = ["en", "fr", "it", "es", "de"]


def parse_combined(path: Path) -> "collections.OrderedDict[int, str]":
    """Parse a combined_<code>.txt file into an {offset: text} map.

    Mirrors scripts/apply_combined_fr.py: skip blanks and ``#`` comments,
    keep only ``0x<hex>: <text>`` lines, last entry wins for duplicate offsets.
    """
    mapping: "collections.OrderedDict[int, str]" = collections.OrderedDict()
    if not path.exists():
        return mapping
    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = LINE_RE.match(line)
            if not match:
                continue
            offset = int(match.group(1), 16)
            mapping[offset] = match.group(2)
    return mapping


def discover_languages() -> "list[str]":
    """All language codes that have a combined_<code>.txt on disk."""
    found = []
    for code in DEFAULT_ORDER:
        if (LANGUAGES_DIR / code / f"combined_{code}.txt").exists():
            found.append(code)
    # any extra languages not in DEFAULT_ORDER
    for child in sorted(LANGUAGES_DIR.glob("*/combined_*.txt")):
        code = child.parent.name
        if code not in found:
            found.append(code)
    return found


def classify(en_text: str, lang_map: "dict[int, str]", offset: int) -> str:
    """Status of one offset for one target language relative to EN."""
    if offset not in lang_map:
        return "missing"
    if lang_map[offset] == en_text:
        return "untranslated"
    return "translated"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--languages",
        help="comma-separated target codes to audit (default: all but en/de)",
    )
    ap.add_argument(
        "--include-de",
        action="store_true",
        help="include German in the audit (excluded by default)",
    )
    ap.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "output" / "audit"),
        help="directory for the CSV exports",
    )
    args = ap.parse_args()

    available = discover_languages()
    if "en" not in available:
        print("ERROR: languages/en/combined_en.txt is required as reference.", file=sys.stderr)
        return 2

    # Load every available language once.
    maps = {code: parse_combined(LANGUAGES_DIR / code / f"combined_{code}.txt") for code in available}
    en = maps["en"]

    # Decide which languages to audit as *targets* (compared against EN).
    if args.languages:
        targets = [c.strip() for c in args.languages.split(",") if c.strip()]
    else:
        targets = [c for c in available if c != "en"]
        if not args.include_de:
            targets = [c for c in targets if c != "de"]
    targets = [c for c in targets if c in maps]

    # Column order for the wide CSV: en first, then targets in DEFAULT_ORDER.
    col_order = ["en"] + [c for c in DEFAULT_ORDER if c in targets] + [
        c for c in targets if c not in DEFAULT_ORDER
    ]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- Per-language statistics -------------------------------------------
    stats = {c: collections.Counter() for c in targets}
    orphans = {c: [] for c in targets}

    all_offsets = sorted(en.keys())
    en_offset_set = set(en.keys())

    # Wide per-offset CSV.
    wide_path = out_dir / "translation_coverage.csv"
    with wide_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        header = ["offset"] + col_order + [f"status_{c}" for c in targets]
        writer.writerow(header)
        for off in all_offsets:
            en_text = en[off]
            row = [f"0x{off:06X}", en_text]
            row += [maps[c].get(off, "") for c in col_order if c != "en"]
            for c in targets:
                status = classify(en_text, maps[c], off)
                stats[c][status] += 1
                row.append(status)
            writer.writerow(row)

    # Orphan offsets (present in a target but not in EN reference).
    for c in targets:
        for off in maps[c].keys():
            if off not in en_offset_set:
                orphans[c].append(off)
                stats[c]["orphan"] += 1

    # ---- Per-target gap files (missing + untranslated) ---------------------
    gap_paths = {}
    for c in targets:
        gap_path = out_dir / f"translation_gaps_{c}.csv"
        gap_paths[c] = gap_path
        with gap_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["offset", "status", "english", c])
            for off in all_offsets:
                status = classify(en[off], maps[c], off)
                if status in ("missing", "untranslated"):
                    writer.writerow([f"0x{off:06X}", status, en[off], maps[c].get(off, "")])

    # ---- Per-target orphan files (offsets unknown to the EN reference) ------
    orphan_paths = {}
    for c in targets:
        if not orphans[c]:
            continue
        orphan_path = out_dir / f"translation_orphans_{c}.csv"
        orphan_paths[c] = orphan_path
        with orphan_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(["offset", c])
            for off in sorted(orphans[c]):
                writer.writerow([f"0x{off:06X}", maps[c][off]])

    # ---- Summary on stdout -------------------------------------------------
    total = len(all_offsets)
    print(f"Translation coverage audit — {total} reference offsets (EN)\n")
    headers = ["lang", "present", "translated", "untranslated", "missing", "orphan", "coverage%"]
    widths = [6, 9, 11, 13, 9, 7, 10]
    print("  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))
    for c in targets:
        s = stats[c]
        present = s["translated"] + s["untranslated"]
        coverage = 100.0 * s["translated"] / total if total else 0.0
        cells = [
            c,
            str(present),
            str(s["translated"]),
            str(s["untranslated"]),
            str(s["missing"]),
            str(s["orphan"]),
            f"{coverage:.1f}",
        ]
        print("  ".join(cell.ljust(w) for cell, w in zip(cells, widths)))

    print(f"\nWide per-offset CSV : {wide_path.relative_to(REPO_ROOT)}")
    for c in targets:
        print(f"Gaps to fill ({c})   : {gap_paths[c].relative_to(REPO_ROOT)}")
    for c in targets:
        if c in orphan_paths:
            print(f"Orphans ({c})        : {orphan_paths[c].relative_to(REPO_ROOT)}  "
                  f"({stats[c]['orphan']} offsets unknown to EN — often garbage/stale)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
