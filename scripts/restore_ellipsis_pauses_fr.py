#!/usr/bin/env python3
"""Restore ellipsis pauses that R-09 wrongly *deleted* (ticket R-09 follow-up #2).

Background
----------
Commit ``d1aaa6f`` (``clean_wordless_quotes_fr.py``) removed the "wordless" quote
glyphs that had crept into ``combined_fr.txt``.  Those quotes were ex-ellipses:
the English source uses byte ``0xB0`` (the FireRed/CFRU font's "…" glyph) for
pauses/hesitation, and the decoder had turned every ``0xB0`` into a straight
double quote ``"`` (U+0022).  After the encoder fix (3ab66ad) a straight ``"``
re-encodes to a *real* curly quote, so those ex-ellipses rendered in-game as a
stray quote with nothing inside.

R-09 *deleted* them.  But deletion throws away the pause the writer intended:
``"Bref" tu vois"`` → ``"Bref tu vois"`` instead of ``"Bref… tu vois"``.  The
user reported a lone quote that "should have stayed as …" and asked to fix every
case of this kind.

Fix
---
For each entry R-09 changed, the *correct* output is the pre-deletion text with
every ex-ellipsis ``"`` turned into ``…`` (the encoder maps ``…`` → ``...`` →
3×0xad, which renders as the ellipsis glyph — there is no single-byte ``…`` in
the FR build, see memory ``unbound-ellipsis-no-single-byte``).

We read the exact before/after pairs from commit ``d1aaa6f`` (the ground truth
for *where* the ellipses were) and, for each offset whose living entry still
holds the deleted form, rewrite it to the ellipsis form.  Two entries were
re-worded after R-09 (species-name fixes Houndoom→Démolosse, Krookodile→
Crocorible); they are handled by applying the same ``"``→``…`` rule to their
*current* text via the recorded deletion sites.

Strings only ever grow (``"`` → ``…``).  Pointer-based dialogue is relocated to
free space by the build pipeline, so run ``09_csv_to_json_v2.py --allow-too-long``
and verify decoded ROM bytes afterwards.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.clean_ellipsis_fr import clean_body  # noqa: E402

COMBINED = REPO / "combined_fr.txt"
R09_COMMIT = "d1aaa6f"
STRAIGHT = '"'  # U+0022 — the decoded ex-ellipsis byte 0xB0
ELLIPSIS = "…"

_OFF = re.compile(r"(0x[0-9a-fA-F]+):(.*)")


def _to_ellipsis(text: str) -> str:
    """Turn ex-ellipsis quotes into '…', then apply the project ellipsis policy
    (collapse runs, normalise spacing — see scripts/clean_ellipsis_fr.py) so a
    burst like ``Toi""""`` becomes a single ``Toi…`` rather than ``Toi…………``."""
    return clean_body(text.replace(STRAIGHT, ELLIPSIS))


def load_r09_pairs() -> dict[str, tuple[str, str]]:
    """Return {offset_lower: (before_with_quotes, after_deleted)} from R-09."""
    diff = subprocess.run(
        ["git", "show", R09_COMMIT, "--", "combined_fr.txt"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    removed: dict[str, str] = {}
    added: dict[str, str] = {}
    for line in diff:
        m = re.match(r"-(0x[0-9a-fA-F]+):(.*)", line)
        if m:
            removed[m.group(1).lower()] = m.group(2)
            continue
        m = re.match(r"\+(0x[0-9a-fA-F]+):(.*)", line)
        if m:
            added[m.group(1).lower()] = m.group(2)
    return {off: (before, added.get(off, "")) for off, before in removed.items()}


def run(apply: bool) -> int:
    pairs = load_r09_pairs()
    lines = COMBINED.read_text(encoding="utf-8").splitlines(keepends=True)

    # Map offset -> list of (line index, body, trailing newline)
    index: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for i, line in enumerate(lines):
        m = _OFF.match(line)
        if not m:
            continue
        off = m.group(1).lower()
        rest = m.group(2)
        index[off].append((i, rest, ""))
    # recompute body/newline cleanly
    index.clear()
    for i, line in enumerate(lines):
        if ":" not in line:
            continue
        off_raw, rest = line.split(":", 1)
        off = off_raw.strip().lower()
        if not off.startswith("0x"):
            continue
        nl = "\n" if rest.endswith("\n") else ""
        body = rest[:-1] if nl else rest
        index[off].append((i, body, nl))

    restored = 0
    reworded: list[str] = []
    already: list[str] = []
    report: list[tuple[str, str, str]] = []

    for off, (before, after) in pairs.items():
        converted = _to_ellipsis(before)
        entries = index.get(off, [])
        if not entries:
            reworded.append(f"{off} (offset absent)")
            continue
        did = False
        for i, body, nl in entries:
            if body == after:
                # deleted form still present -> restore ellipses
                off_raw = lines[i].split(":", 1)[0]
                lines[i] = f"{off_raw}:{converted}{nl}"
                report.append((off, body, converted))
                restored += 1
                did = True
                break
            if body == converted:
                already.append(off)
                did = True
                break
        if not did:
            # re-worded since R-09: restore by re-applying the deletion sites to
            # the living text. Each ex-ellipsis quote in `before` was deleted in
            # `after`; map the surviving anchors onto the living body.
            i, body, nl = entries[-1]
            new_body = _restore_reworded(before, after, body)
            if new_body and new_body != body:
                off_raw = lines[i].split(":", 1)[0]
                lines[i] = f"{off_raw}:{new_body}{nl}"
                report.append((off, body, new_body))
                restored += 1
            else:
                reworded.append(off)

    for off, b, a in report:
        print(f"{off}\n  - {b[:100]!r}\n  + {a[:100]!r}")
    print(f"\n{restored} entries restored to ellipsis.")
    if already:
        print(f"{len(already)} already in ellipsis form (idempotent): "
              + ", ".join(already[:8]) + ("…" if len(already) > 8 else ""))
    if reworded:
        print(f"{len(reworded)} re-worded since R-09 — NOT auto-restored: "
              + ", ".join(reworded))

    if apply and restored:
        COMBINED.write_text("".join(lines), encoding="utf-8")
        print(f"Written to {COMBINED}")
    elif not apply:
        print("(dry-run — pass --apply to write)")
    return restored


def _restore_reworded(before: str, after: str, living: str) -> str:
    """Re-insert ellipses into a body that was re-worded after R-09.

    The deletion (before→after) only removed ``"`` glyphs; word context around
    each quote is preserved. We walk `before`, and for every ``"`` we locate its
    left/right anchors (a few surrounding chars that survive in `living`) and
    splice a ``…`` back in. Falls back to None if anchors are ambiguous.
    """
    result = living
    # Process quotes right-to-left so earlier indices stay valid.
    positions = [m.start() for m in re.finditer(re.escape(STRAIGHT), before)]
    for pos in reversed(positions):
        left = before[max(0, pos - 12):pos]
        right = before[pos + 1:pos + 13]
        # use the longest unique suffix of left present in result
        anchor_l = _unique_suffix(left, result)
        if anchor_l is None:
            return None
        at = result.find(anchor_l) + len(anchor_l)
        if result[at:at + 1] == ELLIPSIS:
            continue  # already restored — keep idempotent
        result = result[:at] + ELLIPSIS + result[at:]
    return clean_body(result)


def _unique_suffix(left: str, hay: str) -> str | None:
    for k in range(len(left), 1, -1):
        suf = left[-k:]
        if hay.count(suf) == 1:
            return suf
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes to combined_fr.txt")
    run(ap.parse_args().apply)
