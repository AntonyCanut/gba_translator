#!/usr/bin/env python3
"""Unify French place names across the three translation layers.

Background
----------
Several Unbound towns ended up with more than one French rendering, which made
the localisation incoherent:

* ``Bellin Town``   -> "Bourg Bellin", "Bellinville" and a bare "Bellin".
* ``Tarmigan Town`` -> "Bourg Tarmigan", "Tarmiganville" and a stray English
  "Tarmigan Town" leftover.
* ``Dresco Town``   -> "Bourg Dresco" (dominant) and two stray "Ville de Dresco".

This one-shot data fix unifies each town to a single name:

* Bellin   -> ``Bellinville``  (explicit request: "change tout pour Bellinville").
* Tarmigan -> ``Tarmigan``      (explicit request: the short bare name is
  preferred over the earlier "-ville" coinage -- shorter and more logical).
* Dresco   -> ``Bourg Dresco``  (dominant form, 41 vs 2).

The fix is applied to the three synchronised layers:
``combined_fr.txt``, the trilingual CSV and the latest ``*_translation_ready.json``.
Only French text is touched -- the English / Spanish source columns are left
untouched. ``Manoir Tarmigan`` / ``Auberge de Tarmigan`` (proper-noun modifiers,
not the town-with-suffix form) are deliberately preserved.

Usage::

    python3 scripts/unify_toponyms_fr.py [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMBINED = ROOT / 'combined_fr.txt'
CSV_PATH = ROOT / 'output/translation/2026-01-15_trilingual_translation.csv'


def translation_jsons() -> list[Path]:
    """All translation_ready snapshots.

    ``make build-fr`` consumes the most recent one by mtime, but parallel
    tickets can add fresher snapshots; unifying every snapshot keeps the build
    correct whichever one is selected and avoids mtime-ordering surprises.
    """
    candidates = sorted(
        (ROOT / 'output' / 'translation').glob('*_translation_ready.json'),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise SystemExit('No *_translation_ready.json found.')
    return candidates


# Separators that can appear between the two words of a name inside ROM text:
# real whitespace (space / newline), the literal break tokens \n \l \p
# (backslash + letter) and raw control tokens such as <0xFA> / <0xFB> used
# when a name wraps across a line.
_SEP = r'(?:\\[nlp]|<0x[0-9A-Fa-f]{2}>|\s)+'

_RULES = [
    # --- Bellin -> Bellinville -------------------------------------------
    (re.compile(r'Bourg' + _SEP + r'Bellin\b'), 'Bellinville'),
    (re.compile(r'\bBellin\b'), 'Bellinville'),
    # --- Tarmigan -> Tarmigan (short bare town name) ----------------------
    # ``Tarmiganville`` is matched WITHOUT a leading word boundary on purpose:
    # COLOR codes render glued to the word (e.g. "{COLOR}ÉTarmiganville"), so a
    # leading \b would sit between two word chars (É|T) and never match.
    (re.compile(r'Bourg' + _SEP + r'Tarmigan\b'), 'Tarmigan'),
    (re.compile(r'Tarmigan' + _SEP + r'Town\b'), 'Tarmigan'),
    (re.compile(r'Tarmiganville'), 'Tarmigan'),
    # --- Dresco -> Bourg Dresco (drop stray "Ville de Dresco") ------------
    (re.compile(r'\bVille de Dresco\b'), 'Bourg Dresco'),
]


def fix_fr(text: str) -> str:
    """Apply the toponym unification rules to a French string."""
    if not text:
        return text
    for pattern, repl in _RULES:
        text = pattern.sub(repl, text)
    return text


def fix_combined(dry: bool) -> int:
    line_re = re.compile(r'^(0x[0-9A-Fa-f]+:\s*)(.*)$', re.DOTALL)
    changed = 0
    out_lines = []
    for line in COMBINED.read_text(encoding='utf-8').splitlines():
        m = line_re.match(line)
        if m:
            new_body = fix_fr(m.group(2))
            if new_body != m.group(2):
                changed += 1
            line = m.group(1) + new_body
        out_lines.append(line)
    if not dry:
        COMBINED.write_text('\n'.join(out_lines) + '\n', encoding='utf-8')
    print(f'combined_fr.txt : {changed} lines changed')
    return changed


def fix_csv(dry: bool) -> int:
    data = CSV_PATH.read_bytes().decode('utf-8-sig')
    rows = list(csv.reader(io.StringIO(data)))
    changed = 0
    for row in rows[1:]:
        if len(row) <= 8:
            continue
        new = fix_fr(row[8])
        if new != row[8]:
            row[8] = new
            changed += 1
    if not dry:
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator='\r\n')
        writer.writerows(rows)
        CSV_PATH.write_bytes(('﻿' + buf.getvalue()).encode('utf-8'))
    print(f'trilingual CSV  : {changed} rows changed')
    return changed


def fix_json(dry: bool) -> int:
    # offset -> real_max_length budget (from CSV) for too_long recomputation
    budget: dict[int, int] = {}
    with CSV_PATH.open(newline='', encoding='utf-8-sig') as handle:
        for row in csv.reader(handle):
            try:
                off = int(row[0], 16)
                budget[off] = int(row[5])
            except (ValueError, IndexError):
                continue

    encoder = None
    try:
        sys.path.insert(0, str(ROOT))
        from src.core.text_codec import TextEncoder  # noqa: WPS433
        encoder = TextEncoder
    except Exception as exc:  # pragma: no cover - metadata only
        print(f'  (note: encoder unavailable, length metadata kept: {exc})')

    total = 0
    for json_path in translation_jsons():
        data = json.loads(json_path.read_text(encoding='utf-8'))
        changed = 0
        for item in data['translations']:
            new = fix_fr(item.get('translation') or '')
            if new == item.get('translation'):
                continue
            item['translation'] = new
            changed += 1
            if encoder is not None:
                length = len(encoder.encode_pokemon(new)) - 1
                item['length'] = length
                orig_len = item.get('original_length')
                if isinstance(orig_len, int):
                    item['padding_used'] = length - orig_len
                cap = budget.get(item['offset'])
                if cap is not None:
                    item['too_long'] = length > cap
        if changed and not dry:
            json_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'
            )
        print(f'{json_path.name} : {changed} entries changed')
        total += changed
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    fix_combined(args.dry_run)
    fix_csv(args.dry_run)
    fix_json(args.dry_run)
    if args.dry_run:
        print('\n(dry-run: no files written)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
