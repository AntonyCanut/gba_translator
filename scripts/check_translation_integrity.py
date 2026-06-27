#!/usr/bin/env python3
"""
Anti-regression guard for FR translations (combined_fr.txt).

Prevents the recurrence of bug c7c1ede: a mass rewrite of
``combined_fr.txt`` that silently reverted world-map labels to their
English/stale form (Fallshore → Ville de Fallshore, Île de la Lune →
Fullmoon Island, etc.).

Verification principle (see ``docs/20_TRANSLATION_PRESERVATION.md``)
--------------------------------------------------------------------
1. ``combined_fr.txt`` is parsed with the **same rule as the build chain**:
   an offset appearing multiple times → **last entry wins**
   (``apply_combined_fr.py`` does ``mapping[offset] = text``). The lowercase
   hex block at the bottom of the file is therefore the live version.
2. For each critical offset, the **resolved** value is checked (last-wins):
   - PRESENCE       : the offset must resolve to a non-empty string;
   - NON-REGRESSION : the value must not be a known English/stale form.

A plain ``grep -c`` is NOT sufficient: c7c1ede did not delete lines, it
rewrote their **value**. The guard checks the resolved value, not the
presence of a line.

Exit code: 0 if everything is compliant, 1 if at least one regression found.

Usage
-----
    python3 scripts/check_translation_integrity.py
    python3 scripts/check_translation_integrity.py --file path/to/combined_fr.txt
    python3 scripts/check_translation_integrity.py --json   # machine-readable JSON report
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# Line format: « 0x<hex>: <FR text> » (same as apply_combined_fr.py).
LINE_RE = re.compile(r"^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$")

DEFAULT_COMBINED = Path(__file__).resolve().parents[1] / "languages/fr/combined_fr.txt"


@dataclass(frozen=True)
class CriticalLabel:
    """A world-map label to protect against EN/stale regression."""

    offset: int
    name: str
    expected_fr: str
    # English or stale forms that constitute a regression (case-insensitive).
    forbidden_forms: tuple[str, ...]


# The 13 world-map labels saved by B-52 (commit c7c1ede had overwritten them).
# These 0xB5xxxx / 0x72xxxx offsets live ONLY in combined_fr.txt: they are
# absent from the trilingual CSV, so invisible to other guards.
CRITICAL_LABELS: tuple[CriticalLabel, ...] = (
    CriticalLabel(0xB500A0, "Bourg Gurun", "Bourg Gurun", ("ourg Gurum", "Bourg Gurum")),
    CriticalLabel(0x721304, "Trou Glacé", "Trou Glacé", ("Icy Hole",)),
    CriticalLabel(0x7214E8, "Île Scintillante", "Île Scintillante", ("Glimmer Island",)),
    CriticalLabel(0x721968, "Ville d'Epidimy", "Ville d'Epidimy", ("Epidimy Town",)),
    CriticalLabel(0xB50214, "Égouts d'Antisis", "Égouts d'Antisis", ("Antisis Sewers",)),
    CriticalLabel(0xB503CC, "Volcan Cendreux", "Volcan Cendreux", ("Cinder Volcano",)),
    CriticalLabel(0xB514E4, "Dehara", "Dehara", ("Dehara City", "Ville de Dehara")),
    CriticalLabel(0xB52274, "Pension Pokémon", "Pension Pokémon", ("Pokemon Day Care", "Pokémon Day Care")),
    CriticalLabel(0xB522A4, "Bourg Polder", "Bourg Polder", ("Polder Town",)),
    CriticalLabel(0xB531D8, "Île du Croissant", "Île du Croissant", ("Newmoon Island",)),
    CriticalLabel(0xB535C8, "Île de la Lune", "Île de la Lune", ("Fullmoon Island",)),
    CriticalLabel(0xB537AC, "Bois-Rouge", "Bois-Rouge", ("Redwood Village", "Redwood village")),
    CriticalLabel(0x720E74, "Fallshore", "Fallshore", ("Ville de Fallshore",)),
)


@dataclass
class LabelResult:
    """Result of a critical label check."""

    label: CriticalLabel
    resolved: Optional[str]
    ok: bool
    reason: str


@dataclass
class IntegrityReport:
    """Overall result of the integrity guard."""

    total_entries: int
    distinct_offsets: int
    duplicate_offsets: int
    results: List[LabelResult] = field(default_factory=list)

    @property
    def failures(self) -> List[LabelResult]:
        return [r for r in self.results if not r.ok]

    @property
    def ok(self) -> bool:
        return not self.failures


def load_last_wins(path: Path) -> tuple[Dict[int, str], int]:
    """Parse combined_fr.txt applying the last-wins rule used by the build chain.

    Returns ``(mapping, total_entries)`` where ``mapping[offset]`` is the **last**
    value encountered (offset case-insensitive, since it is stored as an int).
    """

    mapping: Dict[int, str] = {}
    total = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            match = LINE_RE.match(line.rstrip("\n"))
            if not match:
                continue
            offset = int(match.group(1), 16)
            mapping[offset] = match.group(2).strip()
            total += 1
    return mapping, total


def check_label(label: CriticalLabel, mapping: Dict[int, str]) -> LabelResult:
    """Check presence + non-regression for a critical label."""

    resolved = mapping.get(label.offset)
    if resolved is None:
        return LabelResult(label, None, False, "offset absent from combined_fr.txt")
    if not resolved.strip():
        return LabelResult(label, resolved, False, "empty translation (will not be written to ROM)")
    for bad in label.forbidden_forms:
        if resolved.casefold() == bad.casefold():
            return LabelResult(label, resolved, False, f"regression to forbidden form « {bad} »")
    return LabelResult(label, resolved, True, "ok")


def build_report(path: Path) -> IntegrityReport:
    """Build the integrity report for a given combined_fr.txt."""

    mapping, total = load_last_wins(path)
    distinct = len(mapping)
    results = [check_label(label, mapping) for label in CRITICAL_LABELS]
    return IntegrityReport(
        total_entries=total,
        distinct_offsets=distinct,
        duplicate_offsets=total - distinct,
        results=results,
    )


def _render_human(report: IntegrityReport) -> str:
    lines = [
        "FR translation integrity guard (combined_fr.txt)",
        f"  total entries      : {report.total_entries}",
        f"  distinct offsets   : {report.distinct_offsets}",
        f"  duplicates (last-wins): {report.duplicate_offsets}",
        f"  protected map labels  : {len(report.results)}",
        "",
    ]
    for result in report.results:
        mark = "OK  " if result.ok else "FAIL"
        value = result.resolved if result.resolved is not None else "<absent>"
        lines.append(f"  [{mark}] 0x{result.label.offset:06X} {result.label.name:<18} → « {value} »")
        if not result.ok:
            lines.append(f"         ↳ {result.reason}")
    lines.append("")
    if report.ok:
        lines.append("✅ No map label regressed — combined_fr.txt is compliant.")
    else:
        lines.append(f"❌ {len(report.failures)} label(s) regressed — see docs/20_TRANSLATION_PRESERVATION.md")
    return "\n".join(lines)


def _render_json(report: IntegrityReport) -> str:
    payload = {
        "ok": report.ok,
        "total_entries": report.total_entries,
        "distinct_offsets": report.distinct_offsets,
        "duplicate_offsets": report.duplicate_offsets,
        "labels": [
            {
                "offset": f"0x{r.label.offset:06X}",
                "name": r.label.name,
                "resolved": r.resolved,
                "ok": r.ok,
                "reason": r.reason,
            }
            for r in report.results
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_COMBINED,
        help="path to combined_fr.txt (default: repo root)",
    )
    parser.add_argument("--json", action="store_true", help="emit a machine-readable JSON report")
    args = parser.parse_args(argv)

    if not args.file.exists():
        print(f"error: file not found: {args.file}", file=sys.stderr)
        return 2

    report = build_report(args.file)
    print(_render_json(report) if args.json else _render_human(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
