#!/usr/bin/env python3
r"""Tighten quotes in the FR dialogue: `" mot "` → `"mot"` (ticket R-09 follow-up).

Background
----------
French source entries store quotations with a literal space *inside* the
quotes — `« mot »` (and a few straight-quote cases `" mot "`). In-game both
forms render with the same curly glyph, so the user sees `" mot "` with a
gap hugging each quote. The request: drop the space immediately inside a
quotation so it reads `"mot"`.

Strategy
--------
Walk each entry once and remove a single literal space (U+0020) that sits:

* right *after* an opening quote (`« `, `“ `, `‹ `, opening straight `"`), and
* right *before* a closing quote (` »`, ` ”`, ` ›`, closing straight `"`).

Guillemets and curly quotes are unambiguous (``«“‹`` open, ``»”›`` close).
The straight ``"`` is ambiguous, so its direction alternates per entry
(1st = opening, 2nd = closing, …) — the same pairing the encoder applies.

Only the literal space character is removed; structural breaks (``\n``,
``\l``, ``\p`` — backslash escapes) and the quote glyphs themselves are
never touched. The transform only ever *shortens* a string, so a pointer
can never overflow.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
COMBINED = REPO / "languages/fr/combined_fr.txt"

OPENERS = "«“‹"
CLOSERS = "»”›"
STRAIGHT = '"'  # U+0022 — ambiguous, resolved by per-entry alternation


def strip_inner_quote_spaces(text: str) -> str:
    """Drop a single literal space directly inside each quotation in *text*."""
    out: list[str] = []
    straight_open = True  # next straight quote opens a quotation
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in OPENERS:
            out.append(ch)
            if i + 1 < n and text[i + 1] == " ":
                i += 1  # skip the following space
        elif ch in CLOSERS:
            if out and out[-1] == " ":
                out.pop()  # drop the preceding space
            out.append(ch)
        elif ch == STRAIGHT:
            if straight_open:
                out.append(ch)
                if i + 1 < n and text[i + 1] == " ":
                    i += 1
            else:
                if out and out[-1] == " ":
                    out.pop()
                out.append(ch)
            straight_open = not straight_open
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def run(apply: bool) -> int:
    lines = COMBINED.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = 0
    spaces_removed = 0
    report = []
    for idx, line in enumerate(lines):
        if ":" not in line:
            continue
        offset_hex, rest = line.split(":", 1)
        offset_hex = offset_hex.strip()
        nl = "\n" if rest.endswith("\n") else ""
        body = rest[:-1] if nl else rest
        if not any(q in body for q in OPENERS + CLOSERS + STRAIGHT):
            continue
        new_body = strip_inner_quote_spaces(body)
        if new_body == body:
            continue
        spaces_removed += len(body) - len(new_body)
        changed += 1
        report.append((offset_hex, body.strip(), new_body.strip()))
        lines[idx] = f"{offset_hex}:{new_body}{nl}"

    for off, before, after in report[:40]:
        print(f"{off}\n  - {before[:90]!r}\n  + {after[:90]!r}")
    if len(report) > 40:
        print(f"… and {len(report) - 40} more entries")
    print(f"\n{changed} entries tightened, {spaces_removed} inner-quote spaces removed.")

    if apply and changed:
        COMBINED.write_text("".join(lines), encoding="utf-8")
        print(f"Written to {COMBINED}")
    elif not apply:
        print("(dry-run — pass --apply to write)")
    return changed


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="write changes to combined_fr.txt")
    args = ap.parse_args()
    run(args.apply)
