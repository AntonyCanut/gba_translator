#!/usr/bin/env python3
"""Patch ability-name cells (fixed-width 17-byte table) EN→FR after the build.

The ability-name table starts at file offset 0xA36398 (index 0 = "-------")
with a **stride of 17 bytes** per entry: ``name + 0xFF + zero padding``. It is a
class-2 fixed-width table — no pointers, absent from the injection JSON and the
Spanish extraction — so the translation pipeline never reaches it directly.

The main build's in-place ROM fallback (``prepare_fr_json.py``) *does* translate
an ability name, but only when the French string is **no longer** than the
English original it overwrites. Every French name that is longer than its
English counterpart is silently dropped and ships in English, even though it
fits comfortably inside the 17-byte cell:

    "Ice Body" (8)  → "Corps Gel" (9)      ← the reported bug
    "Dry Skin" (8)  → "Peau Sèche" (10)
    ...and ~130 more.

This patch writes the French ability names straight into their fixed cells,
sourced from ``combined_fr.txt`` (the single EN→FR source of truth) and
validated against ``combined_en.txt`` so a cell is only overwritten when it
currently holds the matching English name (or a de-accented variant of the
French target — self-healing for older builds that transliterated ``œ``→``OE``).

Like ``patch_fixed_table_names.py`` and ``patch_status_abbrevs_fr.py`` this is
committed code wired into ``make build-fr``; it is immune to the volatile
regeneration of ``combined_fr.txt`` and the injection JSON.

Usage:
    python3 scripts/patch_ability_names_fr.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.text.charmap_data import BYTE_TO_CHAR, CHAR_TO_BYTE

# Ability-name table geometry (see module docstring).
#   index 0   → 0xA36398 = "-------" (ABILITY_NONE placeholder)
#   index 292 → 0xA376FC = "Royal Roar" (last ability)
# Beyond 0xA376FC the aligned offsets hold ability *descriptions* and battle
# strings (multi-line, control tokens), NOT names — so the table is bounded
# explicitly rather than walked, to avoid straying into that data.
ABILITY_TABLE_OFFSET = 0xA36398
ABILITY_TABLE_LAST = 0xA376FC
ABILITY_STRIDE = 17

_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")

# Prior FR names we are willing to overwrite when the target changed (so a
# re-run over an already-built ROM self-heals instead of warning-and-skipping).
# 0xA376FC: "Royal Roar" was first shipped as "Rugissement Royal" (17 chars),
# which overflows the 17-byte cell; it is now "Hurlement Royal" (fits cleanly).
_PRIOR_VARIANTS: dict[int, set] = {
    0xA376FC: {"Rugissement Royal"},
}


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


def _decode_cell(data: bytes, offset: int, stride: int = ABILITY_STRIDE) -> str:
    chars = []
    for i in range(stride):
        b = data[offset + i]
        if b == 0xFF:
            break
        chars.append(BYTE_TO_CHAR.get(b, f"<{b:02X}>"))
    return "".join(chars)


def _fold(text: str) -> str:
    """Case- and accent-insensitive fold used to accept de-accented variants."""
    text = text.replace("œ", "oe").replace("Œ", "oe")
    text = text.replace("æ", "ae").replace("Æ", "ae")
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.casefold()


def apply_to_rom(
    data: bytearray,
    fr: dict[int, str],
    en: dict[int, str],
    *,
    base: int = ABILITY_TABLE_OFFSET,
    last: int = ABILITY_TABLE_LAST,
    stride: int = ABILITY_STRIDE,
) -> tuple[int, list[str]]:
    """Patch ability-name cells in place. Returns (patched_count, warnings)."""
    patched = 0
    warnings: list[str] = []

    for offset in range(base, last + 1, stride):
        if offset + stride > len(data):
            break
        fr_text = fr.get(offset)
        if fr_text is None:
            continue  # placeholder cell ("-------", "-") — no FR name

        current = _decode_cell(data, offset, stride)
        if current == fr_text:
            continue  # already the target (idempotent / pipeline in-place hit)

        try:
            fr_bytes = _encode(fr_text)
        except KeyError as exc:
            warnings.append(f"0x{offset:X}: FR {fr_text!r} unencodable ({exc}) — skip")
            continue
        if len(fr_bytes) + 1 > stride:
            warnings.append(
                f"0x{offset:X}: FR {fr_text!r} needs "
                f"{len(fr_bytes) + 1} bytes > {stride}-byte cell — skip"
            )
            continue

        # Only overwrite a cell that still holds the English name, or a
        # de-accented variant of the French target (self-heals older builds
        # that transliterated e.g. "œ"→"OE"). Anything else is left untouched.
        en_text = en.get(offset)
        accepted = (
            current == en_text
            or _fold(current) == _fold(fr_text)
            or current in _PRIOR_VARIANTS.get(offset, set())
        )
        if not accepted:
            warnings.append(
                f"0x{offset:X}: cell holds {current!r} (EN={en_text!r}, "
                f"FR={fr_text!r}) — unexpected, skip"
            )
            continue

        cell = fr_bytes + b"\xff" + bytes(stride - len(fr_bytes) - 1)
        data[offset : offset + stride] = cell
        patched += 1

    return patched, warnings


def apply_patches(
    rom_path: Path,
    combined_fr: Path,
    combined_en: Path,
    dry_run: bool = False,
) -> int:
    fr = _parse_combined(combined_fr)
    en = _parse_combined(combined_en)
    data = bytearray(rom_path.read_bytes())
    patched, warnings = apply_to_rom(data, fr, en)
    for w in warnings:
        print(f"  WARN {w}", file=sys.stderr)
    if patched and not dry_run:
        rom_path.write_bytes(data)
    return patched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    parser.add_argument(
        "--combined",
        type=Path,
        default=Path("languages/fr/combined_fr.txt"),
        help="EN→FR master file the FR ability names are read from.",
    )
    parser.add_argument(
        "--combined-en",
        type=Path,
        default=Path("languages/en/combined_en.txt"),
        help="English master file used to validate each cell before writing.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n = apply_patches(args.rom, args.combined, args.combined_en, dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_ability_names_fr: {n} ability name cell(s) patched{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
