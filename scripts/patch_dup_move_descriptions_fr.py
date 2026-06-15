#!/usr/bin/env python3
"""Repoint the *duplicate* move-description table so the give-CS / move-info
screen never freezes on an unterminated French string.

Pokémon Unbound keeps **two** move-description pointer tables:

* ``0x0899F190`` — the « Capacités connues » summary table, already re-wrapped
  and relocated by :mod:`scripts.patch_move_descriptions_fr`.
* ``0x08488708`` — a second table read by the move-info / give-CS path. The
  generic builder writes the (longer) French descriptions over the original
  English slots here, so a description routinely overruns its slot and
  destroys the **0xFF terminator** of the next entry, fusing a long run of
  descriptions with no terminator at all (≈720 bytes at 0x0848_2ACD).

When the give-CS sequence hands the player a field move, the engine expands
that move's description into a RAM buffer and word-wraps it with CFRU's
``0x089F35F8`` routine, which scans for the 0xFF terminator one byte at a
time (``GetStringWidth`` at ``0x08005Exx``). With no terminator in range the
scan never ends → the CPU spins forever → the game freezes on the « Alors,
prends cette CS… » box, ignoring all input. English never freezes because the
English descriptions all fit their slots and stay terminated.

The fix mirrors :mod:`scripts.patch_move_descriptions_fr`: for every entry of
the duplicate table whose stored string is unterminated (overflowed), take the
authoritative French text — keyed by the entry's original ROM offset in
``combined_fr.txt`` (the source of truth) — re-encode it (the encoder always
appends 0xFF), relocate it into ROM free space and repoint the table cell.
Termination alone removes the infinite loop; the relocated copy can never run
into its neighbour again.
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
DUP_TABLE = 0x08488708          # second move-description pointer table
DUP_TABLE_LEN = 346             # valid ROM pointers in the table
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


def _deref(rom: bytes, table_offset: int) -> int | None:
    value = int.from_bytes(rom[table_offset:table_offset + 4], "little")
    if ROM_POINTER_BASE <= value < ROM_POINTER_BASE + 0x02000000:
        return value - ROM_POINTER_BASE
    return None


def _is_overflow(rom: bytes, offset: int) -> bool:
    """True when no 0xFF terminator is reachable within the slot budget."""
    end = rom.find(b"\xff", offset)
    return end < 0 or end - offset > OVERFLOW_THRESHOLD


def encode_text(text: str) -> bytes:
    """Encode a combined_fr.txt value (literal ``\\n`` -> newline) + terminator."""
    return TextEncoder.encode_pokemon(text.replace("\\n", "\n"))


def apply(rom: bytearray, combined: dict[int, str],
          reserved_rom: bytes | None = None) -> dict:
    allocator = FreeSpaceAllocator(rom, reserved_rom=reserved_rom)
    stats = {"total": 0, "overflow": 0, "relocated": 0,
             "already_ok": 0, "no_source": 0, "failed": 0}

    for i in range(DUP_TABLE_LEN):
        cell = DUP_TABLE + i * 4 - ROM_POINTER_BASE
        target = _deref(rom, cell)
        if target is None:
            continue
        stats["total"] += 1

        if not _is_overflow(rom, target):
            stats["already_ok"] += 1
            continue
        stats["overflow"] += 1

        text = combined.get(target)
        if text is None:
            stats["no_source"] += 1
            continue

        encoded = encode_text(text)
        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            stats["failed"] += 1
            continue
        rom[new_offset:new_offset + len(encoded)] = encoded
        rom[cell:cell + 4] = struct.pack("<I", new_offset + ROM_POINTER_BASE)
        stats["relocated"] += 1

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

    print("✓ Table de descriptions d'attaque dupliquée (anti-freeze give-CS):")
    print(f"   - Entrées valides:     {stats['total']}")
    print(f"   - Déjà terminées:      {stats['already_ok']}")
    print(f"   - En débordement:      {stats['overflow']}")
    print(f"   - Relocalisées:        {stats['relocated']}")
    if stats["no_source"]:
        print(f"   - Sans source:        {stats['no_source']}")
    if stats["failed"]:
        print(f"   - ÉCHECS (free space): {stats['failed']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
