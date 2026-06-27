#!/usr/bin/env python3
"""Check that each move description fits within the summary screen window.

The "Known Moves" screen displays a move description over **5 lines maximum**,
each line staying under ~122 px (≈ 21 characters in the FRLG font). Beyond
that, text overflows: words cut off at the right edge (horizontal) or lines
hidden (vertical) — see ticket screenshots.

This script reads the built FR ROM, decodes each move description via the
``gMoveDescriptionPointers`` pointer table, and lists those that overflow,
so they can be reworked in ``combined_fr.txt``.

Examples
--------
    # Full audit, list only overflowing moves
    python3 scripts/check_move_descriptions.py

    # Show everything (including OK), with per-line detail
    python3 scripts/check_move_descriptions.py --all --verbose

    # Export JSON of moves to rework
    python3 scripts/check_move_descriptions.py --json out/move_overflow.json

    # On a different ROM / with custom thresholds
    python3 scripts/check_move_descriptions.py --rom output/roms/GenedRom-fr.gba \\
        --max-lines 5 --max-width 122

Exit code: 0 if all descriptions fit, 1 if at least one overflows
(usable as a build gate).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.move_description_check import (  # noqa: E402
    MAX_LINES,
    MAX_LINE_WIDTH,
    MoveDescriptionResult,
    check_all_moves,
)

DEFAULT_ROM = Path("output/roms/GenedRom-fr.gba")


def _format_result(result: MoveDescriptionResult, verbose: bool) -> str:
    status = "OK    " if result.fits else "OVERFLOW"
    head = (
        f"[{status}] #{result.index:<3} {result.name:<18} "
        f"{result.line_count} line(s), max {result.max_line_width} px"
    )
    if result.fits and not verbose:
        return head
    parts = [head]
    if not result.fits:
        parts.append("        → " + " ; ".join(result.reasons))
    if verbose or not result.fits:
        for ln in result.lines:
            flag = " «<<" if ln.too_wide else ""
            parts.append(
                f"        {ln.width:3d}px {ln.chars:2d}c | {ln.text!r}{flag}"
            )
    return "\n".join(parts)


def _result_to_dict(result: MoveDescriptionResult) -> dict:
    return {
        "index": result.index,
        "name": result.name,
        "fits": result.fits,
        "line_count": result.line_count,
        "max_line_width": result.max_line_width,
        "reasons": result.reasons,
        "description": result.description,
        "lines": [
            {
                "text": ln.text,
                "width": ln.width,
                "chars": ln.chars,
                "too_wide": ln.too_wide,
            }
            for ln in result.lines
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that move descriptions fit within the summary "
        "screen window (5 lines × ~21 characters)."
    )
    parser.add_argument(
        "--rom",
        type=Path,
        default=DEFAULT_ROM,
        help=f"FR ROM to audit (default: {DEFAULT_ROM})",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=MAX_LINES,
        help=f"Maximum number of lines (default: {MAX_LINES})",
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=MAX_LINE_WIDTH,
        help=f"Maximum line width in pixels (default: {MAX_LINE_WIDTH})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Also show moves that fit (not just overflowing ones)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Detail each line (width in px, characters)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="Write the full report as JSON to this path",
    )
    args = parser.parse_args(argv)

    if not args.rom.is_file():
        parser.error(f"ROM not found: {args.rom}")

    rom = bytearray(args.rom.read_bytes())
    results = check_all_moves(
        rom, max_lines=args.max_lines, max_width=args.max_width
    )
    overflow = [r for r in results if not r.fits]

    shown = results if args.all else overflow
    for result in shown:
        print(_format_result(result, args.verbose))

    print()
    print(
        f"{len(results)} move(s) checked — "
        f"{len(results) - len(overflow)} OK, {len(overflow)} to rework "
        f"(thresholds: {args.max_lines} lines, {args.max_width} px/line)."
    )
    if overflow:
        names = ", ".join(f"{r.name} (#{r.index})" for r in overflow)
        print(f"To rework in combined_fr.txt: {names}")

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "rom": str(args.rom),
            "max_lines": args.max_lines,
            "max_width": args.max_width,
            "total": len(results),
            "overflow_count": len(overflow),
            "moves": [_result_to_dict(r) for r in results],
        }
        args.json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"JSON report written: {args.json}")

    return 1 if overflow else 0


if __name__ == "__main__":
    raise SystemExit(main())
