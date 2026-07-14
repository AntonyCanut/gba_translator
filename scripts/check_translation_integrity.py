#!/usr/bin/env python3
"""
Anti-regression guard for combined_<lang>.txt translation files (all languages).

Single source of truth: ``languages/<lang>/protected_entries.yaml``
-------------------------------------------------------------------
Every translation fix validated through a ticket/GitHub issue is recorded in
the per-language manifest. This guard re-resolves each protected offset in
``combined_<lang>.txt`` (same last-wins rule as the build chain) and fails
unless the resolved value matches the manifest **exactly**.

Why: shared-checkout agents repeatedly commit stale snapshots of the combined
files, silently reverting fixes landed minutes earlier (Pattern C, see
``docs/20_TRANSLATION_PRESERVATION.md`` §7). Historical incidents: c7c1ede
(mass rewrite reverting 13 world-map labels), 9ad0fee (0x1F0F842),
dc84690f (Méga-Cuff templates), 8fe7dddb0 (Hoopa dialogues), and 2d7f7a6
(a *German* fix whose stale snapshot reverted the French issue #67 fix at
0x417396, 18 minutes after it landed).

A plain ``grep -c`` is NOT sufficient: those commits did not delete lines,
they rewrote their **value**. The guard checks the resolved value.

Manifest format (YAML)::

    entries:
      - offset: "0x417396"
        name: "Menu équipe: Sortir (#67)"
        expected: 'Choisis Pokémon ou Sortir.'
        forbidden: ['Choisis Pokémon ou Annuler.']   # optional, better message
      - offset: "0xA4E047"
        name: "Cube sort prompt (#76)"
        absent: true          # the offset must NOT resolve to any entry

To change a protected string on purpose, update ``expected`` in the manifest
in the SAME commit as the ``combined_<lang>.txt`` edit.

Enforcement points:
- pre-commit (husky) → ``make test-python-fast`` → tests/unit/test_translation_integrity.py
- ``make build-fr`` / ``build-it`` / ``build-de`` / ``build-indie`` → ``check-translations-<lang>``

Exit code: 0 compliant, 1 at least one regression, 2 usage/config error.

Usage
-----
    python3 scripts/check_translation_integrity.py                 # all languages
    python3 scripts/check_translation_integrity.py --lang fr       # one language
    python3 scripts/check_translation_integrity.py --json          # machine-readable
    python3 scripts/check_translation_integrity.py --fix           # rewrite combined files from the manifest
    python3 scripts/check_translation_integrity.py --file f.txt --manifest m.yaml
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Line format: « 0x<hex>: <text> » (same as apply_combined_fr.py).
LINE_RE = re.compile(r"^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$")

REPO_ROOT = Path(__file__).resolve().parents[1]
LANGUAGES_DIR = REPO_ROOT / "languages"
MANIFEST_NAME = "protected_entries.yaml"


@dataclass(frozen=True)
class ProtectedEntry:
    """A protected translation entry (or a must-stay-absent offset)."""

    offset: int
    name: str
    expected: Optional[str] = None
    absent: bool = False
    # Known bad/stale forms — matched case-insensitively for a clearer message.
    forbidden: Tuple[str, ...] = ()
    issue: str = ""


@dataclass
class EntryResult:
    """Result of a protected entry check."""

    entry: ProtectedEntry
    resolved: Optional[str]
    ok: bool
    reason: str


@dataclass
class IntegrityReport:
    """Result of the integrity guard for one combined file."""

    lang: str
    combined: Path
    manifest: Path
    total_entries: int
    distinct_offsets: int
    duplicate_offsets: int
    results: List[EntryResult] = field(default_factory=list)

    @property
    def failures(self) -> List[EntryResult]:
        return [r for r in self.results if not r.ok]

    @property
    def ok(self) -> bool:
        return not self.failures


def load_manifest(path: Path) -> Tuple[ProtectedEntry, ...]:
    """Load and validate a protected_entries.yaml manifest."""

    return parse_manifest(yaml.safe_load(path.read_text(encoding="utf-8")) or {}, path)


def parse_manifest(data: Any, path: Path) -> Tuple[ProtectedEntry, ...]:
    """Validate protected-entry data already loaded from YAML."""

    raw_entries = data.get("entries") or []
    entries: List[ProtectedEntry] = []
    for idx, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: entries[{idx}] is not a mapping")
        raw_offset = raw.get("offset")
        if raw_offset is None:
            raise ValueError(f"{path}: entries[{idx}] is missing 'offset'")
        offset = int(raw_offset, 16) if isinstance(raw_offset, str) else int(raw_offset)
        absent = bool(raw.get("absent", False))
        expected = raw.get("expected")
        if absent and expected is not None:
            raise ValueError(f"{path}: entries[{idx}] (0x{offset:X}) has both 'absent' and 'expected'")
        if not absent and (expected is None or not str(expected).strip()):
            raise ValueError(f"{path}: entries[{idx}] (0x{offset:X}) needs a non-empty 'expected' (or absent: true)")
        entries.append(
            ProtectedEntry(
                offset=offset,
                name=str(raw.get("name", f"0x{offset:X}")),
                expected=None if absent else str(expected),
                absent=absent,
                forbidden=tuple(str(f) for f in raw.get("forbidden") or ()),
                issue=str(raw.get("issue", "")),
            )
        )
    seen: Dict[int, int] = {}
    for entry in entries:
        seen[entry.offset] = seen.get(entry.offset, 0) + 1
    dupes = [f"0x{off:X}" for off, count in seen.items() if count > 1]
    if dupes:
        raise ValueError(f"{path}: duplicate protected offsets: {', '.join(dupes)}")
    return tuple(entries)


def discover_languages() -> List[Tuple[str, Path, Path]]:
    """Find every language with a protected-entries manifest.

    Returns ``[(lang, combined_path, manifest_path), ...]`` sorted by lang.
    """

    targets: List[Tuple[str, Path, Path]] = []
    if not LANGUAGES_DIR.is_dir():
        return targets
    for manifest in sorted(LANGUAGES_DIR.glob(f"*/{MANIFEST_NAME}")):
        lang = manifest.parent.name
        combined = manifest.parent / f"combined_{lang}.txt"
        targets.append((lang, combined, manifest))
    return targets


def load_last_wins(path: Path) -> Tuple[Dict[int, str], int]:
    """Parse a combined file applying the last-wins rule used by the build chain.

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


def check_entry(entry: ProtectedEntry, mapping: Dict[int, str]) -> EntryResult:
    """Check one protected entry against the resolved (last-wins) mapping."""

    resolved = mapping.get(entry.offset)
    if entry.absent:
        if resolved is None:
            return EntryResult(entry, None, True, "ok (absent as required)")
        return EntryResult(
            entry, resolved, False,
            "offset must stay ABSENT from the combined file (see manifest) but resolves to a value",
        )
    if resolved is None:
        return EntryResult(entry, None, False, "offset absent from the combined file")
    if not resolved.strip():
        return EntryResult(entry, resolved, False, "empty translation (will not be written to ROM)")
    if resolved == entry.expected:
        return EntryResult(entry, resolved, True, "ok")
    for bad in entry.forbidden:
        if resolved.casefold() == bad.casefold():
            return EntryResult(entry, resolved, False, f"regression to forbidden form « {bad} »")
    return EntryResult(entry, resolved, False, f"does not match the protected value « {entry.expected} »")


def build_report(combined: Path, manifest: Path, lang: str = "?") -> IntegrityReport:
    """Build the integrity report for one combined file + manifest pair."""

    entries = load_manifest(manifest)
    mapping, total = load_last_wins(combined)
    distinct = len(mapping)
    results = [check_entry(entry, mapping) for entry in entries]
    return IntegrityReport(
        lang=lang,
        combined=combined,
        manifest=manifest,
        total_entries=total,
        distinct_offsets=distinct,
        duplicate_offsets=total - distinct,
        results=results,
    )


def apply_fixes(report: IntegrityReport) -> List[str]:
    """Rewrite the combined file so every failing entry matches the manifest.

    Surgical, line-based:
    - wrong value  → rewrite the LAST line for that offset in place;
    - missing      → append at end of file (last-wins ⇒ the new line is live);
    - must-be-absent violated → comment out every line for that offset.

    Returns human-readable descriptions of the fixes applied.
    """

    lines = report.combined.read_text(encoding="utf-8").splitlines(keepends=True)
    # Index every line by offset.
    by_offset: Dict[int, List[int]] = {}
    for lineno, line in enumerate(lines):
        match = LINE_RE.match(line.rstrip("\n"))
        if match:
            by_offset.setdefault(int(match.group(1), 16), []).append(lineno)

    applied: List[str] = []
    appended: List[str] = []
    for result in report.failures:
        entry = result.entry
        occurrences = by_offset.get(entry.offset, [])
        if entry.absent:
            for lineno in occurrences:
                lines[lineno] = f"# [protected:absent {entry.issue or entry.name}] {lines[lineno]}"
            applied.append(f"0x{entry.offset:X}: commented out {len(occurrences)} line(s) (must stay absent)")
        elif occurrences:
            lineno = occurrences[-1]
            eol = "\n" if lines[lineno].endswith("\n") else ""
            lines[lineno] = f"0x{entry.offset:x}: {entry.expected}{eol}"
            applied.append(f"0x{entry.offset:X}: last entry rewritten to the protected value")
        else:
            appended.append(f"0x{entry.offset:x}: {entry.expected}\n")
            applied.append(f"0x{entry.offset:X}: appended (offset was missing)")

    if applied:
        if appended and lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        report.combined.write_text("".join(lines) + "".join(appended), encoding="utf-8")
    return applied


def _render_human(report: IntegrityReport) -> str:
    lines = [
        f"[{report.lang}] translation integrity guard — {report.combined.name}",
        f"  manifest           : {report.manifest.relative_to(REPO_ROOT) if report.manifest.is_relative_to(REPO_ROOT) else report.manifest}",
        f"  total entries      : {report.total_entries}",
        f"  distinct offsets   : {report.distinct_offsets}",
        f"  duplicates (last-wins): {report.duplicate_offsets}",
        f"  protected entries  : {len(report.results)}",
        "",
    ]
    for result in report.results:
        mark = "OK  " if result.ok else "FAIL"
        value = result.resolved if result.resolved is not None else "<absent>"
        lines.append(f"  [{mark}] 0x{result.entry.offset:06X} {result.entry.name:<30} → « {value} »")
        if not result.ok:
            lines.append(f"         ↳ {result.reason}")
    lines.append("")
    if report.ok:
        lines.append(f"✅ [{report.lang}] no protected entry regressed.")
    else:
        lines.append(
            f"❌ [{report.lang}] {len(report.failures)} protected entrie(s) regressed — "
            "see docs/20_TRANSLATION_PRESERVATION.md §7. Intentional change? "
            "Update languages/<lang>/protected_entries.yaml in the same commit. "
            "Restore from the manifest with: python3 scripts/check_translation_integrity.py --fix"
        )
    return "\n".join(lines)


def _report_payload(report: IntegrityReport) -> dict:
    return {
        "lang": report.lang,
        "combined": str(report.combined),
        "ok": report.ok,
        "total_entries": report.total_entries,
        "distinct_offsets": report.distinct_offsets,
        "duplicate_offsets": report.duplicate_offsets,
        "entries": [
            {
                "offset": f"0x{r.entry.offset:06X}",
                "name": r.entry.name,
                "issue": r.entry.issue,
                "resolved": r.resolved,
                "ok": r.ok,
                "reason": r.reason,
            }
            for r in report.results
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lang", help="check a single language (e.g. fr, it, de)")
    parser.add_argument("--file", type=Path, help="explicit combined file (requires --manifest)")
    parser.add_argument("--manifest", type=Path, help="explicit manifest (used with --file)")
    parser.add_argument("--json", action="store_true", help="emit a machine-readable JSON report")
    parser.add_argument("--fix", action="store_true", help="rewrite combined files so protected entries match the manifest")
    args = parser.parse_args(argv)

    if args.file or args.manifest:
        if not (args.file and args.manifest):
            print("error: --file and --manifest must be used together", file=sys.stderr)
            return 2
        targets = [(args.lang or "custom", args.file, args.manifest)]
    else:
        targets = discover_languages()
        if args.lang:
            targets = [t for t in targets if t[0] == args.lang]
        if not targets:
            print(
                f"error: no {MANIFEST_NAME} manifest found"
                + (f" for language '{args.lang}'" if args.lang else "")
                + f" under {LANGUAGES_DIR}",
                file=sys.stderr,
            )
            return 2

    reports: List[IntegrityReport] = []
    for lang, combined, manifest in targets:
        for path, kind in ((combined, "combined file"), (manifest, "manifest")):
            if not path.exists():
                print(f"error: [{lang}] {kind} not found: {path}", file=sys.stderr)
                return 2
        report = build_report(combined, manifest, lang)
        if args.fix and not report.ok:
            for description in apply_fixes(report):
                print(f"[fix][{lang}] {description}")
            report = build_report(combined, manifest, lang)
        reports.append(report)

    if args.json:
        print(json.dumps({"ok": all(r.ok for r in reports), "languages": [_report_payload(r) for r in reports]}, ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(_render_human(r) for r in reports))
    return 0 if all(r.ok for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
