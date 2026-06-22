#!/usr/bin/env python3
"""Audit every dialogue in ``combined_fr.txt`` for the arrow-at-line-start rule.

Pokemon Unbound world-map / route sign panels use the directional arrow glyphs
(0x79 ↑, 0x7A ↓, 0x7B ←, 0x7C →) to point at a destination name. In the English
source EVERY arrow that belongs to a sign panel sits at the *start of a line* —
it is either the first byte of the string or it immediately follows a line-break
control code (\\n = 0xFE newline, \\l = 0xFA scroll, \\p = 0xFB page). The
destination name then trails the arrow on the same line.

When a panel was machine-translated the reflow sometimes pushed a line break in
front of the arrow (``name <arrow>\\n dest``) or buried the arrow mid-line
(``name <arrow> dest``), so the rendered sign lost its arrow / line break. This
audit walks the *live* entry for every offset (``combined_fr.txt`` keeps the last
duplicate, so the lowercase / fix blocks at the end of the file win) and reports
any arrow that is not at a line start.

Not every 0x79-0x7C byte is a directional sign arrow, though:

* inline colored icons in prose — e.g. the "Trainer Tips" string renders
  ``A green {FC:0106}↑{FC:0102} indicates …`` with the arrow mid-sentence;
* arrow bytes that fall inside a textbox / sprite control-code header;
* arrow bytes that are just coincidental bytes inside non-text data.

To tell a real sign panel from those, the audit is **English-grounded**: an
offset is only checked when the English original at that same offset is itself a
panel (it has at least one arrow and *all* of its arrows are at a line start).
For every other offset the English arrow is mid-line too, so a mid-line French
arrow is faithful, not a regression, and is skipped. This mirrors the truth used
everywhere in this repo: the English ROM is the reference.

Usage:
    python3 scripts/audit_arrow_line_start_fr.py [combined_fr.txt] [--english ROM]
    python3 scripts/audit_arrow_line_start_fr.py --source-only   # skip EN grounding
Exit code 0 when clean, 1 when at least one misplaced arrow is found.
"""
from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

ARROW_BYTES = {0x79, 0x7A, 0x7B, 0x7C}
LINE_BREAK_BYTES = {0xFA, 0xFB, 0xFE}  # \l scroll, \p page, \n newline
# Source escapes that map to single-byte line-break control codes.
BREAK_ESCAPES = {"n": 0xFE, "l": 0xFA, "p": 0xFB}
# Brace tokens that also encode to a line-break control code.
BREAK_BRACES = {"PAGE", "SCROLL", "NEWLINE", "LINE", "CLEAR"}

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COMBINED = REPO_ROOT / "combined_fr.txt"
DEFAULT_ENGLISH = REPO_ROOT / "input/roms/englishrom.gba"
ROM_POINTER_BASE = 0x08000000

GLYPH = {0x79: "↑", 0x7A: "↓", 0x7B: "←", 0x7C: "→"}
_ENTRY_RE = re.compile(r"^\s*(0x[0-9A-Fa-f]+)\s*:\s*(.*)$")


def load_live_entries(path: Path) -> dict[int, tuple[str, int]]:
    """Return ``{offset_int: (text, line_number)}`` keeping the LAST duplicate.

    ``combined_fr.txt`` may list the same offset several times; the build honours
    the final occurrence, so the audit must too. Comments and blanks are skipped.
    """
    live: dict[int, tuple[str, int]] = {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _ENTRY_RE.match(line)
        if not m:
            continue
        live[int(m.group(1), 16)] = (m.group(2), lineno)
    return live


def find_misplaced_arrows(text: str) -> list[tuple[int, str]]:
    """Tokenise ``text`` into its byte stream and return misplaced arrows.

    Returns ``(arrow_byte, context)`` for every arrow that is NOT at a line
    start. ``at_line_start`` is true at the string start and immediately after a
    line-break byte; any other emitted byte clears it.
    """
    misplaced: list[tuple[int, str]] = []
    at_line_start = True
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if text.startswith("<0x", i):  # raw byte placeholder <0xNN>
            j = text.find(">", i)
            if j != -1:
                try:
                    byte = int(text[i + 3 : j], 16)
                except ValueError:
                    byte = -1
                if byte in ARROW_BYTES:
                    if not at_line_start:
                        misplaced.append((byte, text[max(0, i - 16) : j + 12]))
                    at_line_start = False
                else:
                    at_line_start = byte in LINE_BREAK_BYTES
                i = j + 1
                continue
        if ch == "\\" and i + 1 < n:  # \n \l \p line breaks (other escapes literal)
            at_line_start = text[i + 1] in BREAK_ESCAPES
            i += 2
            continue
        if ch == "{":  # {NAME} control token
            j = text.find("}", i)
            if j != -1:
                at_line_start = text[i + 1 : j].split(":")[0] in BREAK_BRACES
                i = j + 1
                continue
        at_line_start = False  # any other character emits a non-break byte
        i += 1
    return misplaced


def english_is_panel(rom: bytes, offset: int, limit: int = 256) -> bool:
    """True when the English string at ``offset`` is a sign panel.

    A panel has at least one directional arrow and every arrow sits at a line
    start (first byte or right after a 0xFA/0xFB/0xFE break). Inline icons,
    control-header arrows and non-text data fail this test.
    """
    if offset < 0 or offset >= len(rom):
        return False
    end = rom.find(b"\xff", offset, offset + limit)
    raw = rom[offset : end if end != -1 else offset + limit]
    arrows = [k for k, b in enumerate(raw) if b in ARROW_BYTES]
    if not arrows:
        return False
    return all(k == 0 or raw[k - 1] in LINE_BREAK_BYTES for k in arrows)


def audit(
    path: Path, english_rom: bytes | None = None
) -> list[tuple[int, int, str, list[tuple[int, str]]]]:
    """Return ``(offset, lineno, text, misplaced)`` for every offending entry.

    When ``english_rom`` is given, offsets whose English original is not itself a
    panel are skipped (inline icons / control headers / non-text bytes).
    """
    findings = []
    for offset, (text, lineno) in load_live_entries(path).items():
        misplaced = find_misplaced_arrows(text)
        if not misplaced:
            continue
        if english_rom is not None and not english_is_panel(english_rom, offset):
            continue
        findings.append((offset, lineno, text, misplaced))
    findings.sort(key=lambda f: f[0])
    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Arrow-at-line-start audit")
    parser.add_argument("combined", nargs="?", default=str(DEFAULT_COMBINED))
    parser.add_argument("--english", default=str(DEFAULT_ENGLISH),
                        help="English ROM used to ground panel detection")
    parser.add_argument("--source-only", action="store_true",
                        help="Skip English grounding (flags every mid-line arrow)")
    args = parser.parse_args(argv[1:])

    path = Path(args.combined)
    if not path.exists():
        print(f"combined_fr.txt not found: {path}", file=sys.stderr)
        return 2
    english_rom = None
    if not args.source_only:
        en_path = Path(args.english)
        if en_path.exists():
            english_rom = en_path.read_bytes()
        else:
            print(f"note: English ROM not found ({en_path}); running source-only",
                file=sys.stderr)

    findings = audit(path, english_rom)
    if not findings:
        print("OK: every directional sign arrow sits at a line start.")
        return 0
    print(f"FAIL: {len(findings)} dialogue(s) with misplaced arrow(s):\n")
    for offset, lineno, text, misplaced in findings:
        print(f"  0x{offset:07X} (line {lineno})")
        for byte, ctx in misplaced:
            print(f"    {GLYPH[byte]} 0x{byte:02X} not at line start: …{ctx}…")
        print(f"    full: {text}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
