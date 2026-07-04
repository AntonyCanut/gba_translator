#!/usr/bin/env python3
"""Patch move-name cells (fixed-width 13-byte table) after the build.

The real, engine-read move-name table (``gMoveNames``-equivalent) lives at
file offset **0x1B2980**, stride 13 bytes (``name + 0xFF + zero padding``),
covering all 894 move slots (index 0 = "no move" placeholder "-", indices
1..893 = the CFRU-expanded move roster — the same ``MOVE_COUNT`` as
:mod:`src.core.moves`, which owns the *description* pointer table).

This address was **not** where a translator-authored dataset expected it.
``combined_it.txt`` (and, historically, whoever first captured this table)
recorded move names at ``0xA40A10`` (stride 13, same 894 entries) — call it
the *legacy offset*. That address is **not the live table**: it sits inside
the generic builder's Pokédex-description free-space pool, and every build
(the pristine ``englishrom.gba`` reference *and* the FR/IT/DE output ROMs
alike) currently holds an unrelated, already-relocated Pokédex flavour-text
fragment there (confirmed by direct byte inspection — see B-165-adjacent
ticket "IT: move names + ability descriptions have zero patch coverage").
Writing move names at the legacy address would silently corrupt that live
Pokédex text; this patch never touches it.

The real table at 0x1B2980 is, bafflingly, already filled with **French**
names in every build sampled (the pristine reference ROM included), which
is why FR needs no patch here (the content already matches) while IT and DE
currently ship French move names instead of English or their own language —
the actual highest-visibility symptom behind the "zero patch coverage"
ticket, worse than the originally-reported "renders English".

This patch maps each legacy-offset entry in ``--combined`` to its move index
and writes the translated name at the *real* table cell, so it can reuse
already-authored ``combined_it.txt`` text without re-translating anything.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import BYTE_TO_CHAR, CHAR_TO_BYTE

# Real, live move-name table (see module docstring). Verified by direct ROM
# inspection: decodes to the canonical Gen1+ move order ("-", "Écras'Face"
# aka Pound-FR, "Poing Karaté" aka Karate Chop-FR, …) across every sampled
# build, and its last non-placeholder entry lands exactly at index 893 —
# matching src.core.moves.MOVE_COUNT (894, entry 0 = "no move").
MOVE_NAME_TABLE = 0x1B2980
MOVE_STRIDE = 13
MOVE_COUNT = 894

# Legacy offset scheme used by the translator-authored datasets (never the
# live table — see module docstring). Every combined_<code>.txt move-name
# entry was recorded here, at the same stride/count as the real table, so a
# plain per-index remap recovers the intended text.
LEGACY_TABLE_OFFSET = 0xA40A10

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
    live_base: int = MOVE_NAME_TABLE,
    stride: int = MOVE_STRIDE,
    count: int = MOVE_COUNT,
) -> tuple[int, list[str]]:
    """Patch move-name cells in place. Returns (patched_count, warnings)."""
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
