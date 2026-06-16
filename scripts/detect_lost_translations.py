#!/usr/bin/env python3
"""
Detect French translation work that was silently lost in combined_fr.txt.

Background
----------
``combined_fr.txt`` is the master EN→FR file. Fixes get lost in two recurring
ways (see tasks/lessons and test_location_names_fr.py):

  1. A commit that regenerates/reorders the file collaterally *deletes* clean
     French entries (e.g. c7c1ede wiped 36 region/label lines while fixing one
     dialogue line). If nobody re-adds them, the offset reverts to English
     in-game.
  2. Duplicate offsets — the build uses the *last* entry for a given offset
     ("last wins"). A later, cruder append can clobber an earlier hand-polished
     translation.

This script walks the git history of combined_fr.txt and reports, for the last
N commits, every *clean French* entry that was deleted and never restored
(its offset is absent from the current file and its text appears nowhere else).
Garbage/mojibake extraction lines are filtered out.

Usage::

    python3 scripts/detect_lost_translations.py [--commits 50] [--all]

Exit code is non-zero when losses are found, so it can gate CI.
"""

from __future__ import annotations

import argparse
import collections
import re
import subprocess
import sys
from pathlib import Path

LINE_RE = re.compile(r"^(0x[0-9A-Fa-f]+):\s?(.*)$")
ACCENTS = "éèêëàâçùûüîïôœÉÈÊÀÂÇÙÛÜÎÏÔŒ«»’…"
FR_WORDS = re.compile(
    r"\b(le|la|les|un|une|des|de|du|et|est|pas|vous|tu|ne|que|qui|pour|avec|"
    r"sur|dans|son|sa|ses|au|aux|je|il|elle|ce|cette|plus|tout|mais|comme|"
    r"bien|peut|alors|ici|même|reçu|soigner|capitale|ville)\b",
    re.I,
)


def _is_clean_french(text: str) -> bool:
    """True for readable French; False for mojibake / byte-image garbage."""
    core = re.sub(r"\{[^}]*\}|<[^>]*>|\\[nplNPL]", "", text)
    if len(core.strip()) < 6:
        return False
    # Reject any exotic codepoint (CJK / half-width kana / box glyphs).
    if any(ord(c) > 0x2000 and c not in ACCENTS and c not in "’…«»—" for c in core):
        return False
    good = sum(
        1
        for c in core
        if c.isalnum() or c in " '’.,!?:;-—«»…()\"\n" or c in ACCENTS
    )
    if good / max(1, len(core)) < 0.92:
        return False
    return len(FR_WORDS.findall(text)) >= 2


def _git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=True
    ).stdout


def _parse(text: str) -> "collections.OrderedDict[int, str]":
    out: "collections.OrderedDict[int, str]" = collections.OrderedDict()
    for line in text.splitlines():
        m = LINE_RE.match(line)
        if m:
            out[int(m.group(1), 16)] = m.group(2)  # last wins
    return out


def find_lost(path: str, commits: int | None) -> list[tuple[int, str, str]]:
    current = _parse(Path(path).read_text(encoding="utf-8"))
    current_offsets = set(current)
    current_texts = {v.strip() for v in current.values()}

    rev_args = ["log", "--format=%H", "--", path]
    if commits:
        window = set(_git(["rev-list", f"-{commits}", "HEAD"]).split())
    else:
        window = None

    deleted: dict[tuple[int, str], str] = {}
    for sha in _git(rev_args).split():
        if window is not None and sha not in window:
            continue
        diff = _git(["show", sha, "--", path])
        added, removed = set(), {}
        for line in diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                m = LINE_RE.match(line[1:])
                if m:
                    added.add((int(m.group(1), 16), m.group(2)))
            elif line.startswith("-") and not line.startswith("---"):
                m = LINE_RE.match(line[1:])
                if m:
                    removed[(int(m.group(1), 16), m.group(2))] = sha
        for key, sha2 in removed.items():
            if key not in added:
                deleted.setdefault(key, sha2)

    lost = []
    for (offset, value), sha in deleted.items():
        if offset in current_offsets:
            continue
        if value.strip() in current_texts:
            continue
        if not _is_clean_french(value):
            continue
        lost.append((offset, value, sha))
    return sorted(lost)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--combined", default="combined_fr.txt", help="Path to combined_fr.txt"
    )
    parser.add_argument(
        "--commits", type=int, default=50, help="How many recent commits to scan"
    )
    parser.add_argument(
        "--all", action="store_true", help="Scan the entire history (ignore --commits)"
    )
    args = parser.parse_args()

    lost = find_lost(args.combined, None if args.all else args.commits)
    scope = "entire history" if args.all else f"last {args.commits} commits"
    if not lost:
        print(f"✓ No lost clean-French entries found ({scope}).")
        return 0

    print(f"✗ {len(lost)} lost clean-French entrie(s) found ({scope}):\n")
    for offset, value, sha in lost:
        msg = _git(["log", "-1", "--format=%s", sha]).strip()
        print(f"0x{offset:06X}  deleted by {sha[:7]} — {msg[:60]}")
        print(f"    {value[:110]}")
    print("\nRe-add the offending entries to combined_fr.txt (living block).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
