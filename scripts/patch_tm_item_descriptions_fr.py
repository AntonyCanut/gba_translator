#!/usr/bin/env python3
"""Relocate the French TM/HM (CT/CS) item descriptions so the bag never freezes.

Every Technical Machine / Hidden Machine item (``CT63``, ``CT94``, ``CS08`` …)
stores its bag description behind a pointer at ``+0x14`` of its 44-byte entry in
the item table (``0x876074``). In the English ROM these point into a tightly
packed move-description region around ``0xA3xxxx`` whose slots are tiny — several
are empty (a lone ``0xFF``).

The inline-overrides pass writes the French description **in place** at those
offsets. Because the French text is far longer than the English slot, it spills
past its terminator and clobbers the next entries: the whole region collapses
into one long run with the ``0xFF`` terminators destroyed (e.g. ``CT94`` reads
``…une gemme ou unUne graine inquiétante…`` — Calcination fused into Vampigraine,
Suc Digestif, …). When the bag renders such a description, ``GetStringWidth``
scans for a ``0xFF`` that never comes → **infinite loop → frozen screen**
(reported as the "Volcan Cendre" freeze when picking up CT94 to the left).

This post-build step gives every CT/CS item its own self-contained, terminated
copy of the authoritative French description (from ``combined_fr.txt``), placed
in ROM free space, and repoints the item entry at it. The encoder always appends
the ``0xFF`` terminator, so a relocated description can never run into its
neighbour again. It runs after the move-description patches and is idempotent:
once an item points outside the fused region it is left alone.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.text_codec import TextDecoder, TextEncoder
from src.core.text_reinserter import FreeSpaceAllocator

ROM_POINTER_BASE = 0x08000000

# Item table layout (see scripts/patch_item_names_fr.py).
ITEM_TABLE_BASE = 0x876074
ITEM_STRIDE = 44
ITEM_NAME_LEN = 14
DESC_PTR_OFFSET = 0x14

# The packed move-description region the TM/HM descriptions point into and
# overflow within. Only pointers inside this window are repaired, which makes
# the pass idempotent (a relocated description points into free space, well
# outside this range, and is skipped on the next run).
FUSED_REGION = (0xA30000, 0xA50000)

# A description that reaches its 0xFF within this many bytes is self-contained
# and renders fine — leave it in place. The longest authoritative French TM/HM
# description encodes to 107 bytes, and the fused/over-long runs that freeze the
# bag all reach 133+ bytes (or never terminate), so this budget cleanly tells
# the two apart. Relocating only the broken descriptions keeps every healthy
# entry byte-identical to English (notably the give-CS gift item 0x1B5, whose
# obtain box renders the static name, not this description).
OVERFLOW_BUDGET = 120

# Technical/Hidden machine items render their move description in the bag and
# are the only consumers of the fused region; guard by name so no ordinary item
# is ever touched. "CT" = Capsule Technique (TM), "CS" = Capacité Secrète (HM).
MACHINE_PREFIXES = ("CT", "CS")

DEFAULT_COMBINED = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
LINE_RE = re.compile(r"\s*0x([0-9a-fA-F]+)\s*:\s*(.*)")


def _deref(rom: bytes, offset: int):
    if offset + 4 > len(rom):
        return None
    value = int.from_bytes(rom[offset:offset + 4], "little")
    if ROM_POINTER_BASE <= value < ROM_POINTER_BASE + 0x02000000:
        return value - ROM_POINTER_BASE
    return None


def _normalize(text: str) -> str:
    """Mirror apply_inline_overrides_fr's escape handling.

    The TM/HM descriptions are plain text with only ``\\n`` breaks (no scroll
    codes or {tokens}); convert them to real newlines so the encoder emits the
    0xFE line-break control code.
    """
    return text.replace("\\n", "\n").replace("\\l", "<0xFA>").replace("\\p", "<0xFB>")


def load_combined(path: Path) -> dict:
    """offset -> authoritative French text (last entry wins, per repo rules)."""
    mapping: dict[int, str] = {}
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = LINE_RE.match(line.rstrip("\n"))
            if not match:
                continue
            mapping[int(match.group(1), 16)] = match.group(2)
    return mapping


def _item_name(rom: bytes, base: int) -> str:
    return TextDecoder.decode_pokemon(rom[base:base + ITEM_NAME_LEN])


def apply(rom: bytearray, combined: dict, reserved_rom: bytes | None = None) -> dict:
    """Relocate every CT/CS description out of the fused region (rom mutated)."""
    allocator = FreeSpaceAllocator(rom, reserved_rom=reserved_rom)
    stats = {"machines": 0, "relocated": 0, "skipped_outside": 0,
             "in_place_ok": 0, "missing_text": 0, "failed": 0}

    i = 0
    while True:
        base = ITEM_TABLE_BASE + i * ITEM_STRIDE
        if base + ITEM_STRIDE > len(rom):
            break
        i += 1

        name = _item_name(rom, base)
        if not name.startswith(MACHINE_PREFIXES):
            continue
        stats["machines"] += 1

        ptr = _deref(rom, base + DESC_PTR_OFFSET)
        if ptr is None or not (FUSED_REGION[0] <= ptr < FUSED_REGION[1]):
            stats["skipped_outside"] += 1
            continue

        # Only the over-long / unterminated (fused) descriptions freeze the bag.
        # A short, properly terminated description renders fine and is left
        # byte-identical to English — never relocate a healthy entry.
        if rom.find(b"\xff", ptr, ptr + OVERFLOW_BUDGET + 1) >= 0:
            stats["in_place_ok"] += 1
            continue

        text = combined.get(ptr)
        if not text:
            stats["missing_text"] += 1
            continue

        encoded = TextEncoder.encode_pokemon(_normalize(text))
        new_offset = allocator.allocate(len(encoded))
        if new_offset is None:
            stats["failed"] += 1
            continue
        rom[new_offset:new_offset + len(encoded)] = encoded
        rom[base + DESC_PTR_OFFSET:base + DESC_PTR_OFFSET + 4] = struct.pack(
            "<I", new_offset + ROM_POINTER_BASE
        )
        stats["relocated"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, help="Built French ROM to patch in place")
    parser.add_argument("--combined", default=str(DEFAULT_COMBINED),
                        help="combined_fr.txt (authoritative French descriptions)")
    parser.add_argument("--reference-rom", default=None,
                        help="Same-base ROM whose populated bytes must not be reused as free space")
    args = parser.parse_args()

    rom_path = Path(args.rom)
    rom = bytearray(rom_path.read_bytes())
    combined = load_combined(Path(args.combined))
    reserved = Path(args.reference_rom).read_bytes() if args.reference_rom else None

    stats = apply(rom, combined, reserved_rom=reserved)
    rom_path.write_bytes(rom)

    print("✓ Descriptions d'objets CT/CS (anti-freeze sac):")
    print(f"   - Machines (CT/CS):   {stats['machines']}")
    print(f"   - Relocalisées:       {stats['relocated']}")
    print(f"   - Saines (en place):  {stats['in_place_ok']}")
    print(f"   - Hors zone fusionnée:{stats['skipped_outside']}")
    if stats["missing_text"]:
        print(f"   - Texte manquant:     {stats['missing_text']}")
    if stats["failed"]:
        print(f"   - ÉCHECS (free space):{stats['failed']}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
