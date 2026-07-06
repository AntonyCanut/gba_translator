#!/usr/bin/env python3
"""Patch move-name cells (fixed-width 13-byte table) after the build.

The move-name table (``gMoveNames``-equivalent) is a fixed-width block, stride
13 bytes (``name + 0xFF + zero padding``), covering all 894 move slots (index
0 = "no move" placeholder "-", indices 1..893 = the CFRU-expanded move roster
— the same ``MOVE_COUNT`` as :mod:`src.core.moves`, which owns the
*description* pointer table). It is reached via index arithmetic from a base
pointer that the engine loads from a fixed code site, **not** by chasing a
per-entry pointer — so its live file offset depends on which base ROM the
build ran against:

* On the **clean vanilla base** (``input/roms/englishrom.gba`` after R-17 — the
  base every non-FR language now builds on) the live table sits at its stock
  address **0xA40A10**, holding English names ("-", "Pound", "Karate Chop", …).
* On the old **French-patched base** (now ``input/roms/patchedfrenchrom.gba``,
  used only by ``build-fr``) the FR build had **relocated** the whole table to
  free space at **0x1B2980** and repointed all 41 code references there; the
  stock 0xA40A10 is left blank (0xFF). This is why an earlier revision of this
  patch hard-coded 0x1B2980 as "the real table" — that was only ever true for
  the contaminated base. On the clean base 0x1B2980 is unreferenced free space,
  so writing there is a silent no-op (the bug this module now fixes).

Every ``combined_<code>.txt`` records move names at **0xA40A10** (the stock /
clean-base offset), used purely as a dict key here. Rather than trust either
hard-coded address, :func:`resolve_live_base` reads the live table pointer
straight from the ROM being patched (code site :data:`MOVE_NAME_PTR_SITE`),
so the same code is correct on the clean base (→ 0xA40A10) and on the
French-patched base (→ 0x1B2980) alike. Each combined entry is mapped by move
index and written at the corresponding *live* table cell.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import BYTE_TO_CHAR, CHAR_TO_BYTE

MOVE_STRIDE = 13
MOVE_COUNT = 894

# Stock / clean-base move-name table offset. Also the key scheme every
# ``combined_<code>.txt`` records move names under (index 0 at this offset,
# index i at +i*13). On the clean vanilla base this IS the live table.
LEGACY_TABLE_OFFSET = 0xA40A10

# Where the old French-patched build relocated the table (free space). Kept as
# a named constant for tests and for the resolver's cross-check; on the clean
# base this address is unreferenced 0xFF free space.
RELOCATED_TABLE_OFFSET = 0x1B2980

# Backwards-compatible alias. Historically this named "the live table"; it is
# really only the French-patched-base relocation target (see module docstring).
MOVE_NAME_TABLE = RELOCATED_TABLE_OFFSET

# Fixed code site holding the 32-bit LE pointer the engine loads to reach the
# move-name table (one of 41 identical references; this one is word-aligned and
# well past the ROM header). Identical file offset on the clean base and the
# French-patched base — only the *value* differs (clean → 0x08A40A10,
# patched → 0x081B2980), so reading it recovers whichever table the engine
# actually reads on THIS rom.
MOVE_NAME_PTR_SITE = 0x000308A4
ROM_POINTER_BASE = 0x08000000
# Index-0 cell is the "no move" placeholder "-" (glyph 0xAE) followed by 0xFF;
# used to sanity-check a resolved base before trusting it.
PLACEHOLDER_BYTE = 0xAE

_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def resolve_live_base(data: bytes, fallback: int = LEGACY_TABLE_OFFSET) -> int:
    """Return the live move-name table base offset for ``data``.

    Reads the table pointer from :data:`MOVE_NAME_PTR_SITE` and validates that
    the target begins with the ``"-"`` placeholder cell (0xAE, 0xFF). Falls
    back to ``fallback`` (the stock/clean-base offset) if the pointer is
    out of range or fails the placeholder check, so a corrupted or unexpected
    ROM degrades to the vanilla address rather than writing somewhere unsafe.
    """
    if MOVE_NAME_PTR_SITE + 4 > len(data):
        return fallback
    ptr = int.from_bytes(data[MOVE_NAME_PTR_SITE : MOVE_NAME_PTR_SITE + 4], "little")
    base = ptr - ROM_POINTER_BASE
    if not (0 <= base <= len(data) - MOVE_STRIDE * MOVE_COUNT):
        return fallback
    if data[base] != PLACEHOLDER_BYTE or data[base + 1] != 0xFF:
        return fallback
    return base


def _parse_combined(path: Path) -> dict[int, str]:
    """Parse ``0x<offset>: text`` lines; last entry wins (case-insensitive)."""
    entries: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _LINE_RE.match(line)
        if m:
            entries[int(m.group(1), 16)] = m.group(2)
    return entries


def _encode(name: str) -> bytes:
    return bytes(CHAR_TO_BYTE[c] for c in name)


def _decode_cell(data: bytes, offset: int, stride: int = MOVE_STRIDE) -> str:
    chars = []
    for i in range(stride):
        b = data[offset + i]
        if b == 0xFF:
            break
        chars.append(BYTE_TO_CHAR.get(b, f"<{b:02X}>"))
    return "".join(chars)


def apply_to_rom(
    data: bytearray,
    translations: dict[int, str],
    *,
    legacy_base: int = LEGACY_TABLE_OFFSET,
    live_base: int | None = None,
    stride: int = MOVE_STRIDE,
    count: int = MOVE_COUNT,
) -> tuple[int, list[str]]:
    """Patch move-name cells in place. Returns (patched_count, warnings).

    ``live_base`` defaults to :func:`resolve_live_base` (the table address the
    engine actually reads on ``data``); pass an explicit value to target a
    specific offset (e.g. in unit tests).
    """
    if live_base is None:
        live_base = resolve_live_base(data)
    patched = 0
    warnings: list[str] = []

    for index in range(count):
        legacy_offset = legacy_base + index * stride
        text = translations.get(legacy_offset)
        if text is None:
            continue  # no authored translation for this move index

        live_offset = live_base + index * stride
        if live_offset + stride > len(data):
            break

        current = _decode_cell(data, live_offset, stride)
        if current == text:
            continue  # already the target (idempotent)

        try:
            encoded = _encode(text)
        except KeyError as exc:
            warnings.append(f"index {index} (0x{live_offset:X}): {text!r} unencodable ({exc}) — skip")
            continue
        if len(encoded) + 1 > stride:
            warnings.append(
                f"index {index} (0x{live_offset:X}): {text!r} needs "
                f"{len(encoded) + 1} bytes > {stride}-byte cell — skip"
            )
            continue

        cell = encoded + b"\xff" + bytes(stride - len(encoded) - 1)
        data[live_offset : live_offset + stride] = cell
        patched += 1

    return patched, warnings


def apply_patches(rom_path: Path, combined: Path, dry_run: bool = False) -> int:
    translations = _parse_combined(combined)
    data = bytearray(rom_path.read_bytes())
    live_base = resolve_live_base(data)
    print(f"patch_move_names: live table @ 0x{live_base:X}", file=sys.stderr)
    patched, warnings = apply_to_rom(data, translations, live_base=live_base)
    for w in warnings:
        print(f"  WARN {w}", file=sys.stderr)
    if patched and not dry_run:
        rom_path.write_bytes(data)
    return patched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument(
        "--combined",
        type=Path,
        required=True,
        help="combined_<code>.txt the move names are read from (legacy 0xA40A10 offset scheme).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n = apply_patches(args.rom, args.combined, dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_move_names: {n} move name cell(s) patched{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
