#!/usr/bin/env python3
"""Stop the give-CS / move-info freeze by terminating **every** reference to the
duplicate move-description data block.

Pokémon Unbound keeps the move descriptions in several places:

* ``0x0899F190`` — the « Capacités connues » summary table, re-wrapped and
  relocated by :mod:`scripts.patch_move_descriptions_fr`.
* a second copy of the descriptions packed contiguously in the original
  English data block at ``~0x08482xxx``. The generic builder writes the
  (longer) French descriptions over the original English slots here, so a
  description routinely overruns its slot and destroys the **0xFF terminator**
  of the next entry, fusing a long run of descriptions with no terminator at
  all (≈720 bytes at 0x0848_2ACD).

That block is referenced by **more than one** pointer table/struct:

* ``0x08488708`` — move-info pointer table (346 entries),
* ``0x08904000`` — a *third* parallel move-description pointer table,
* per-field-move info structs (e.g. ``0x083DEA80`` / ``0x0887AD30``) whose
  description pointer field is read when an NPC hands the player a field move
  (the « give-CS » path).

When the give-CS sequence hands the player a field move, the engine expands
that move's description into ``gStringVar4`` and word-wraps it with CFRU's
``0x089F35F8`` routine, which scans for the 0xFF terminator one byte at a time
(``GetStringWidth`` at ``0x08005Exx``). With no terminator in range the scan
never ends → the CPU spins forever (observed PC ``0x08006xxx``) → the game
freezes on the « Alors, prends cette CS pour aller le voir. » box, ignoring all
input. English never freezes because the English descriptions all fit their
slots and stay terminated.

The earlier version of this script repointed **only** ``0x08488708``. The
give-CS path reads the description through the field-move struct / third table,
which still pointed into the fused block — so the freeze survived a rebuild.

This version is reference-driven instead of table-driven: it scans the whole
ROM for every word-aligned pointer into the move-description block, and for
each *overflowing* target it relocates the authoritative French text (keyed by
the entry's original ROM offset in ``combined_fr.txt``, re-encoded so the
encoder appends 0xFF) into free space **once**, then repoints **every**
reference to that entry. No consumer is left pointing at an unterminated
string, regardless of which table or struct reads it.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.text_codec import TextEncoder
from src.core.text_reinserter import FreeSpaceAllocator

ROM_POINTER_BASE = 0x08000000
# Original English move-description data block that the FR build overwrites in
# place. Pointers into this range that lost their terminator are what freeze the
# word-wrap. Bounds are generous; only *overflowing* targets are touched.
MOVE_DESC_BLOCK = (0x08482000, 0x08484000)
# A genuine move description fits the move-info window in well under this many
# bytes; anything longer means the slot lost its 0xFF terminator (overflow).
OVERFLOW_THRESHOLD = 160
DEFAULT_COMBINED = Path(__file__).resolve().parent.parent / "combined_fr.txt"

_OFFSET_LINE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def load_combined(path: Path) -> dict[int, str]:
    """original ROM offset -> French text (last entry wins, per combined_fr.txt)."""
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _OFFSET_LINE.match(line)
        if m:
            mapping[int(m.group(1), 16)] = m.group(2)
    return mapping


def _is_overflow(rom: bytes, offset: int) -> bool:
    """True when no 0xFF terminator is reachable within the slot budget."""
    end = rom.find(b"\xff", offset)
    return end < 0 or end - offset > OVERFLOW_THRESHOLD


def encode_text(text: str) -> bytes:
    """Encode a combined_fr.txt value (literal ``\\n`` -> newline) + terminator."""
    return TextEncoder.encode_pokemon(text.replace("\\n", "\n"))


def find_block_xrefs(rom: bytes) -> dict[int, list[int]]:
    """Map every move-description block target -> list of word-aligned pointer cells.

    Pointers into ``0x0848xxxx`` are stored little-endian as ``YY YY 48 08``, so we
    only have to look at positions where the high half-word is ``48 08``.
    """
    lo, hi = MOVE_DESC_BLOCK
    refs: dict[int, list[int]] = {}
    needle = b"\x48\x08"
    start = 0
    while True:
        i = rom.find(needle, start)
        if i < 0:
            break
        start = i + 1
        cell = i - 2  # the 4-byte pointer begins two bytes before the high half
        if cell < 0 or cell % 4 != 0:
            continue
        value = int.from_bytes(rom[cell:cell + 4], "little")
        if lo <= value < hi:
            refs.setdefault(value, []).append(cell)
    return refs


def apply(rom: bytearray, combined: dict[int, str],
          reserved_rom: bytes | None = None) -> dict:
    allocator = FreeSpaceAllocator(rom, reserved_rom=reserved_rom)
    refs = find_block_xrefs(rom)
    stats = {"targets": 0, "overflow": 0, "relocated": 0, "repointed": 0,
             "already_ok": 0, "no_source": 0, "failed": 0}
    relocated: dict[int, int] = {}  # original ptr -> new ptr

    for target in sorted(refs):
        stats["targets"] += 1
        offset = target - ROM_POINTER_BASE

        if not _is_overflow(rom, offset):
            stats["already_ok"] += 1
            continue
        stats["overflow"] += 1

        if target not in relocated:
            text = combined.get(offset)
            if text is None:
                stats["no_source"] += 1
                continue
            encoded = encode_text(text)
            new_offset = allocator.allocate(len(encoded))
            if new_offset is None:
                stats["failed"] += 1
                continue
            rom[new_offset:new_offset + len(encoded)] = encoded
            relocated[target] = new_offset + ROM_POINTER_BASE
            stats["relocated"] += 1

        new_ptr = relocated[target]
        for cell in refs[target]:
            rom[cell:cell + 4] = struct.pack("<I", new_ptr)
            stats["repointed"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, help="Built French ROM to patch in place")
    parser.add_argument("--combined", default=str(DEFAULT_COMBINED),
                        help="combined_fr.txt source of truth (offset -> FR text)")
    parser.add_argument("--reference-rom", default=None,
                        help="Same-base ROM whose populated bytes must not be reused as free space")
    args = parser.parse_args()

    rom_path = Path(args.rom)
    rom = bytearray(rom_path.read_bytes())
    combined = load_combined(Path(args.combined))
    reserved = Path(args.reference_rom).read_bytes() if args.reference_rom else None

    stats = apply(rom, combined, reserved_rom=reserved)
    rom_path.write_bytes(rom)

    print("✓ Bloc de descriptions d'attaque dupliqué (anti-freeze give-CS):")
    print(f"   - Cibles référencées:  {stats['targets']}")
    print(f"   - Déjà terminées:      {stats['already_ok']}")
    print(f"   - En débordement:      {stats['overflow']}")
    print(f"   - Relocalisées:        {stats['relocated']}")
    print(f"   - Pointeurs repointés: {stats['repointed']}")
    if stats["no_source"]:
        print(f"   - Sans source:        {stats['no_source']}")
    if stats["failed"]:
        print(f"   - ÉCHECS (free space): {stats['failed']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
