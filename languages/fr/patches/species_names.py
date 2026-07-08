#!/usr/bin/env python3
"""Patch species-name cells (fixed-width 11-byte table) after the build.

The species-name table (``gSpeciesNames``) is a fixed-width block, stride
11 bytes (``name + 0xFF + zero padding``), covering all 1293 species slots
(index 0 = "???" placeholder, indices 1..1292 = the CFRU-expanded species roster).
It is located at a fixed offset (not dynamically resolved like move names).

Every ``combined_<code>.txt`` records species names at **0x166A997** (the stock
offset), used as a dict key. Each combined entry is mapped by species index
and written at the corresponding table cell.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import BYTE_TO_CHAR, CHAR_TO_BYTE

SPECIES_STRIDE = 11
SPECIES_COUNT = 1293

# Fixed offset of the species-name table. Also the key scheme every
# ``combined_<code>.txt`` records species names under (index 0 at this offset,
# index i at +i*11).
TABLE_OFFSET = 0x166A997

_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


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


def _decode_cell(data: bytes, offset: int, stride: int = SPECIES_STRIDE) -> str:
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
    table_base: int = TABLE_OFFSET,
    stride: int = SPECIES_STRIDE,
    count: int = SPECIES_COUNT,
) -> tuple[int, list[str]]:
    """Patch species-name cells in place. Returns (patched_count, warnings)."""
    patched = 0
    warnings: list[str] = []

    for index in range(count):
        offset = table_base + index * stride
        text = translations.get(offset)
        if text is None:
            continue  # no authored translation for this species index

        if offset + stride > len(data):
            break

        current = _decode_cell(data, offset, stride)
        if current == text:
            continue  # already the target (idempotent)

        try:
            encoded = _encode(text)
        except KeyError as exc:
            warnings.append(f"index {index} (0x{offset:X}): {text!r} unencodable ({exc}) — skip")
            continue
        if len(encoded) + 1 > stride:
            warnings.append(
                f"index {index} (0x{offset:X}): {text!r} needs "
                f"{len(encoded) + 1} bytes > {stride}-byte cell — skip"
            )
            continue

        cell = encoded + b"\xff" + bytes(stride - len(encoded) - 1)
        data[offset : offset + stride] = cell
        patched += 1

    return patched, warnings


def apply_patches(rom_path: Path, combined: Path, dry_run: bool = False) -> int:
    translations = _parse_combined(combined)
    data = bytearray(rom_path.read_bytes())
    print(f"patch_species_names: table @ 0x{TABLE_OFFSET:X}", file=sys.stderr)
    patched, warnings = apply_to_rom(data, translations)
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
        help="combined_<code>.txt the species names are read from (0x166A997 offset scheme).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n = apply_patches(args.rom, args.combined, dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_species_names: {n} species name cell(s) patched{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
