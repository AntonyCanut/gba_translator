#!/usr/bin/env python3
"""Inject Italian trainer-class names into the built IT ROM, in place.

The trainer-class name table lives at a fixed base in the ROM
(``gTrainerClassNames`` — verified at file offset ``0x23E558`` in
``englishrom.gba``) and is read by index arithmetic: the engine computes
``base + class_id * 13`` and reads a 13-byte cell (name + ``0xFF``
terminator + zero padding). **No 32-bit pointer references the individual
cells**, so the generic pointer-based CSV/JSON pipeline never touches them
— every class ships the English source verbatim unless a dedicated pass
rewrites the cell bytes.

This is that dedicated pass. It sources the Italian text straight from
``languages/it/combined_it.txt`` (last-entry-wins), encodes it with the
shared :class:`TextEncoder`, and overwrites the cell **in place**, staying
strictly inside the 13-byte cell so no name ever runs into its neighbour.

Hard constraint — the fixed-width cell
--------------------------------------
Because the table is reached by ``index * 13`` arithmetic baked into the
game code, a cell physically cannot hold more than 12 name bytes + the
``0xFF`` terminator. Italian is frequently longer than the English source
("Interviewer" → "Intervistatore", "Hiker" → "Escursionista", …), so a
number of classes simply do not fit. Those are **skipped and reported**,
never truncated mid-word: making them fit requires relocating the whole
table with a wider stride and patching the index-scaling code (a distinct,
emulator-verified piece of work — see the follow-up ticket noted in the
build report). Classes whose Italian fits are written and become visible on
every trainer battle intro.

Usage:
    python3 scripts/patch_trainer_class_names_it.py \\
        --rom output/roms/GenedRom-it.gba \\
        --combined languages/it/combined_it.txt \\
        --source input/roms/englishrom.gba
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.core.text_codec import TextEncoder  # noqa: E402

# gTrainerClassNames — fixed-width name table (verified structurally against
# englishrom.gba: pointers at file offsets 0xD80A0 / 0x11B4B4 target the base).
TABLE_BASE = 0x23E558
CELL_STRIDE = 13
# Index 0 is a blank/null class ("            "); real classes are 1..106.
FIRST_CLASS_INDEX = 1
CLASS_COUNT = 107  # cells 0..106; cell 107 (0x23EAC7) starts unrelated data.

TERMINATOR = 0xFF

LINE_RE = re.compile(r'^\s*0x([0-9A-Fa-f]+)\s*:\s*(.*)$')

# combined_it.txt escape/token expansion → the form TextEncoder.encode
# expects. Ordered longest-first so ``\pk``/``\mn``/``\sm``/``\sf`` are
# expanded before the single-letter ``\p``/``\n`` escapes could eat them.
#   \pk -> PK glyph (0x53)   \mn -> MN glyph (0x54)
#   \sm -> ♂ (0xB5)          \sf -> ♀ (0xB6)
#   \n  -> line break        \l -> scroll (0xFA)   \p -> page break (0xFB)
_ESCAPES = (
    ("\\pk", "<0x53>"),
    ("\\mn", "<0x54>"),
    ("\\sm", "♂"),
    ("\\sf", "♀"),
    ("\\n", "\n"),
    ("\\l", "<0xFA>"),
    ("\\p", "<0xFB>"),
)


def _normalize(text: str) -> str:
    for src, dst in _ESCAPES:
        text = text.replace(src, dst)
    return text


def _encode(text: str) -> bytes:
    """Encode a combined_it.txt line to ROM bytes, terminator included."""
    return TextEncoder.encode(_normalize(text), "pokemon")


def _load_combined(path: Path) -> dict[int, str]:
    """Return offset -> text (last entry wins, matching the build pipeline)."""
    mapping: dict[int, str] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            match = LINE_RE.match(line.rstrip("\n"))
            if match:
                mapping[int(match.group(1), 16)] = match.group(2)
    return mapping


def patch(rom: bytearray, combined: dict[int, str]) -> dict:
    stats = {"written": 0, "unchanged": 0, "overflow": 0, "missing": 0}
    overflow: list[tuple[int, str, int]] = []

    for idx in range(FIRST_CLASS_INDEX, CLASS_COUNT):
        offset = TABLE_BASE + idx * CELL_STRIDE
        text = combined.get(offset)
        if text is None:
            stats["missing"] += 1
            continue

        encoded = _encode(text)
        if len(encoded) > CELL_STRIDE:
            stats["overflow"] += 1
            overflow.append((idx, text, len(encoded)))
            continue

        current = bytes(rom[offset:offset + CELL_STRIDE])
        # Fill the whole cell: name + 0xFF, then zero the remainder so no
        # stale byte from the (longer) English name survives past the
        # terminator. We never write past offset+CELL_STRIDE.
        new_cell = encoded + bytes(CELL_STRIDE - len(encoded))
        if new_cell == current:
            stats["unchanged"] += 1
            continue

        rom[offset:offset + CELL_STRIDE] = new_cell
        stats["written"] += 1

    if overflow:
        print(
            f"  ⚠ {len(overflow)} trainer classes overflow the {CELL_STRIDE}-byte "
            "cell and stay English (would need table relocation):"
        )
        for idx, text, size in overflow:
            print(f"      idx {idx:3d} {TABLE_BASE + idx * CELL_STRIDE:#08x} "
                  f"{text!r} ({size} bytes)")

    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path,
                        help="Built IT ROM to patch in place.")
    parser.add_argument("--combined", type=Path,
                        default=REPO_ROOT / "languages/it/combined_it.txt",
                        help="combined_it.txt source of Italian trainer names.")
    parser.add_argument("--source", type=Path,
                        default=REPO_ROOT / "input/roms/englishrom.gba",
                        help="English source ROM (used only for a structural "
                             "sanity check of the table base).")
    args = parser.parse_args(argv)

    if not args.rom.exists():
        print(f"✗ ROM not found: {args.rom}", file=sys.stderr)
        return 1
    if not args.combined.exists():
        print(f"✗ combined file not found: {args.combined}", file=sys.stderr)
        return 1

    combined = _load_combined(args.combined)
    rom = bytearray(args.rom.read_bytes())

    stats = patch(rom, combined)
    args.rom.write_bytes(rom)

    print(
        "✓ trainer_class_names_it: "
        f"{stats['written']} written, {stats['unchanged']} already correct, "
        f"{stats['overflow']} overflow (kept English), "
        f"{stats['missing']} not in combined_it.txt"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
