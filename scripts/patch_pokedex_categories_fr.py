#!/usr/bin/env python3
"""Translate Pokédex species categories to French and render them as
``"Pokémon <Category>"`` (FR build).

──────────────────────────────────────────────────────────────────────────
The bug this fixes
──────────────────────────────────────────────────────────────────────────

The Pokédex info screen shows a species *category* under the name, e.g.
Pikachu is the "Mouse Pokémon".  Unbound stores the category noun in a
fixed cell and the engine appends the constant " Pokémon" after it, so the
English screen reads ``<noun> Pokémon``.  Two problems for French:

  1. The noun is English ("Mouse", "Seed", …) and some Unbound categories
     are even glued together ("WaterLizard") because the cell is tiny.
  2. The desired French order is *"Pokémon Souris"* (the official French
     Pokédex order), not *"Souris Pokémon"*.

──────────────────────────────────────────────────────────────────────────
Where the category really lives (verified against the source ROM)
──────────────────────────────────────────────────────────────────────────

The renderer reads the category from a table the CFRU lookup at
``0x965bbf4`` computes as ``national_dex_index * 36 + 0x081A357CC``.  So the
category for dex #N is the 0xFF-terminated string at::

    CAT_TABLE_BASE + N * CAT_TABLE_STRIDE      (file offset)

with text at record start (+0x00).  The numeric height/weight/scale fields
begin at **+0x0C**, and the parallel description-pointer table
(``0x1A35800``) is interleaved into the records' tails — so only the first
12 bytes (``+0x00 .. +0x0B``: 11 chars + terminator) may be written.  The
renderer's copy loop independently caps the category at 11 bytes, matching
this cell size.  (Note: this is NOT the same offset combined_fr.txt used —
those entries pointed 2 bytes early into a different table view and never
rendered.)

──────────────────────────────────────────────────────────────────────────
What this patch does
──────────────────────────────────────────────────────────────────────────

1. **Cells** — for every dex record whose English category is in
   ``data/pokedex_categories_fr.json`` it writes the French noun (≤ 11
   bytes) + 0xFF at the record start, zero-filling the rest of the 12-byte
   cell and never touching the numeric fields at +0x0C.

2. **Word order** — the category print routine at ``0x105800`` prints the
   category buffer, measures its width, then prints the " Pokémon" suffix
   after it.  Three 2-byte Thumb edits swap the two prints so the constant
   is rendered *first* and the category *second*; the constant string at
   ``0x415F8F`` is flipped from " Pokémon" (leading space) to "Pokémon "
   (trailing space).  Result on screen: ``Pokémon Souris``.

   Swap detail (all same-size, in-place):
     - 0x10588C  ``add r2,sp,#8`` → ``ldr r2,[pc,#0x30]``  (print const 1st)
     - 0x105896  ``add r1,sp,#8`` → ``ldr r1,[pc,#0x28]``  (measure const)
     - 0x1058A4  ``ldr r2,[pc,#0x18]`` → ``add r2,sp,#8``   (print cell 2nd)
   The const pointer literal lives at 0x1058C0 (= 0x08415F8F); the PC-rel
   offsets above target it from each instruction.

Every patch verifies the bytes it expects and is idempotent.

Usage::

    python3 scripts/patch_pokedex_categories_fr.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core.text_codec import TextDecoder, TextEncoder

ROM_POINTER_BASE = 0x08000000
TERMINATOR = 0xFF

# Category table the renderer actually reads (see module docstring).
CAT_TABLE_BASE = 0x1A357CC
CAT_TABLE_STRIDE = 36
CAT_CELL_LEN = 12          # 11 chars + 0xFF terminator; numeric fields at +0x0C
CAT_MAX_INDEX = 1100       # upper bound; junk/invalid records are skipped

DEFAULT_MAP = Path(__file__).resolve().parents[1] / "data" / "pokedex_categories_fr.json"

# ── Thumb reorder: print the constant first, the category cell second ───────
# These three 2-byte edits are identical in the source EN ROM and the built FR
# ROM (the build never patches this code).
CODE_PATCHES: list[tuple[int, bytes, bytes]] = [
    (0x10588C, bytes.fromhex("02aa"), bytes.fromhex("0c4a")),  # ldr r2,[pc,#0x30]
    (0x105896, bytes.fromhex("02a9"), bytes.fromhex("0a49")),  # ldr r1,[pc,#0x28]
    (0x1058A4, bytes.fromhex("064a"), bytes.fromhex("02aa")),  # add r2,sp,#8
]

# ── Suffix string flip: render "Pokémon " (trailing space) as a PREFIX ──────
# The renderer's literal points at 0x08415F8F.  We need that string to be
# "Pokémon " + 0xFF terminator so the reordered routine prints "Pokémon "
# then the category.  The bytes there depend on the build stage:
#   * EN source:  "\x00Pokémon\xFF"  (leading space; 0x00 = space in CFRU)
#   * built FR:   "Pokémon\xFF\xFF"  (the build already dropped the space ->
#                 this is exactly the glued "MousePokémon" bug we fix)
# Either way we overwrite the 9-byte window with the canonical trailing-space
# form, leaving the adjacent "Ta"/"Ht" label at 0x415F98 untouched.
SUFFIX_OFFSET = 0x415F8F
_SUFFIX_POKEMON = bytes.fromhex("cae3df1be1e3e2")          # "Pokémon"
_SUFFIX_NEW = _SUFFIX_POKEMON + b"\x00\xff"                # "Pokémon " + terminator
_SUFFIX_OLD_FORMS = {
    bytes.fromhex("cae3df1be1e3e2ffff"),                   # built FR ("Pokémon"\xFF\xFF)
    bytes.fromhex("00cae3df1be1e3e2ff"),                   # EN source (" Pokémon"\xFF)
}


def apply_suffix(rom: bytearray) -> int:
    """Flip the dex " Pokémon" suffix string to "Pokémon " (trailing space).

    Tolerant of both the EN-source and built-FR byte layouts; idempotent.
    Returns 1 if it wrote, 0 if already canonical.
    """
    window = bytes(rom[SUFFIX_OFFSET:SUFFIX_OFFSET + len(_SUFFIX_NEW)])
    if window == _SUFFIX_NEW:
        return 0  # already patched
    if window not in _SUFFIX_OLD_FORMS:
        raise ValueError(
            f"0x{SUFFIX_OFFSET:X}: unexpected suffix bytes {window.hex(' ')}"
        )
    rom[SUFFIX_OFFSET:SUFFIX_OFFSET + len(_SUFFIX_NEW)] = _SUFFIX_NEW
    return 1


def load_map(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["categories"] if isinstance(payload, dict) and "categories" in payload else payload


def _decode_cell(data: bytes, offset: int) -> str | None:
    end = data.find(bytes([TERMINATOR]), offset)
    if end < 0 or end - offset > CAT_CELL_LEN:
        return None
    return TextDecoder.decode_pokemon(data[offset:end], preserve_unknown=True)


def apply_code_patches(rom: bytearray) -> int:
    applied = 0
    for offset, old, new in CODE_PATCHES:
        if len(old) != len(new):
            raise ValueError(f"0x{offset:X}: length mismatch")
        cur = bytes(rom[offset:offset + len(old)])
        if cur == new:
            continue  # idempotent
        if cur != old:
            raise ValueError(
                f"0x{offset:X}: unexpected bytes {cur.hex(' ')} (expected {old.hex(' ')})"
            )
        rom[offset:offset + len(new)] = new
        applied += 1
    return applied


def apply_cells(rom: bytearray, fr_map: dict) -> dict:
    stats = {"translated": 0, "already": 0, "untranslated": 0, "skipped": 0}
    for index in range(CAT_MAX_INDEX):
        offset = CAT_TABLE_BASE + index * CAT_TABLE_STRIDE
        if offset + CAT_CELL_LEN > len(rom):
            break
        english = _decode_cell(rom, offset)
        if english is None:
            stats["skipped"] += 1
            continue
        french = fr_map.get(english)
        if french is None:
            # Already-French (idempotent re-run) or genuinely unmapped record.
            if english in fr_map.values():
                stats["already"] += 1
            else:
                stats["untranslated"] += 1
            continue
        encoded = TextEncoder.encode_pokemon(french)  # includes 0xFF terminator
        if len(encoded) > CAT_CELL_LEN:
            raise ValueError(
                f"#{index} {english!r}->{french!r}: {len(encoded)} bytes exceeds cell {CAT_CELL_LEN}"
            )
        cell = encoded + b"\x00" * (CAT_CELL_LEN - len(encoded))
        rom[offset:offset + CAT_CELL_LEN] = cell  # never touches +0x0C numeric fields
        stats["translated"] += 1
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"),
                        help="Built French ROM to patch in place")
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP,
                        help="EN->FR category map JSON")
    args = parser.parse_args()

    rom = bytearray(args.rom.read_bytes())
    fr_map = load_map(args.map)

    code_applied = apply_code_patches(rom)
    code_applied += apply_suffix(rom)
    stats = apply_cells(rom, fr_map)
    args.rom.write_bytes(rom)

    print("✓ Pokédex catégories FR :")
    print(f"   - Réordonnancement code : {code_applied}/{len(CODE_PATCHES) + 1} patch(s)")
    print(f"   - Cellules traduites    : {stats['translated']}")
    print(f"   - Déjà en français      : {stats['already']}")
    print(f"   - Sans traduction       : {stats['untranslated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
