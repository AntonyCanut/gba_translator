#!/usr/bin/env python3
"""Patch trainer-foe name display: "L'adversaire X" → "X adverse".

The CFRU battle engine always writes NAME_WITH_PREFIX as prefix+nickname.  To
reverse the order we use two Thumb code caves in free ROM space (0x1D89C /
0x1D8E4).  Each cave is called via BL from the six per-character exit points of
the NAME_WITH_PREFIX handler:

  Cave A (target 0xD82AA) — used by 0xD7BB4
  Cave B (target 0xD82A4) — used by 0xD7C94 / 0xD7D08 / 0xD7D7C / 0xD7DF0 / 0xD7E64

The two sites use different outer-loop entry points because 0xD7BB4 inlines the
pixel-width accumulation (r0 = width*100 + r_accum) before branching to 0xD82AA,
while the other five rely on 0xD82A4 to perform that computation.

At each call-site the cave checks:
  1. bit 3 of gBattleTypeFlags (0x02022B4C): 1 = trainer battle
  2. [r2] == 0xFF: r2 points to the NEXT nickname char; 0xFF = just wrote last char

When both conditions hold it writes " adverse" (CFRU: 00 D5 D8 EA D9 E6 E7 D9)
to (r8 + r6) — the current dest-buffer position — and increments r6 by 8.

The "L'adversaire " prefix string at 0xA4C61A (and the no-space form at 0xA4C64C)
are emptied by changing their first byte to 0xFF so the prefix copy loop writes
nothing.

Usage:
    python3 scripts/patch_battle_prefix_fr.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---------------------------------------------------------------------------
# BL encoding helper
# ---------------------------------------------------------------------------

def _bl(site: int, target: int) -> bytes:
    """Encode a 4-byte Thumb BL from *site* to *target* (file offsets)."""
    pc = site + 4
    offset = target - pc
    if not (-0x400000 <= offset < 0x400000):
        raise ValueError(f"BL out of range: 0x{site:X} → 0x{target:X}")
    imm_hi = (offset >> 12) & 0x7FF
    imm_lo = (offset >> 1) & 0x7FF
    return struct.pack("<HH", 0xF000 | imm_hi, 0xF800 | imm_lo)


# ---------------------------------------------------------------------------
# Code cave builder
# ---------------------------------------------------------------------------
#
# Register protocol at cave entry (same for all six sites):
#   r0  — pixel-width result (must be preserved)
#   r1  — pixel-width of current char (must be preserved)
#   r2  — ptr to NEXT nickname char (read-only; 0xFF when last char written)
#   r3-r5 — scratch (saved/restored by cave)
#   r6  — dest_idx in output buffer (incremented by 8 when suffix appended)
#   r8  — dest base address (high register; read-only in cave)
#
# " adverse" in CFRU: space=0x00 a=0xD5 d=0xD8 v=0xEA e=0xD9 r=0xE6 s=0xE7 e=0xD9

_ADVERSE = bytes([0x00, 0xD5, 0xD8, 0xEA, 0xD9, 0xE6, 0xE7, 0xD9])
_FLAGS   = 0x02022B4C   # gBattleTypeFlags (GBA RAM)
_ROM_BASE = 0x08000000


def _make_cave(outer_loop_file: int) -> bytes:
    """Build a 72-byte Thumb cave that branches to outer_loop_file."""
    outer_gba = _ROM_BASE + outer_loop_file + 1  # +1 = Thumb interworking

    cave = bytearray(72)

    def h(off: int, val: int) -> None:
        struct.pack_into("<H", cave, off, val)

    def w(off: int, val: int) -> None:
        struct.pack_into("<I", cave, off, val)

    # 00: PUSH {r3, r4, r5}
    h(0x00, 0xB438)
    # 02: LDR r3, [PC, #60]   → literal at cave+0x40 (_FLAGS addr)
    #     PC at 0x02 is treated as 0x04 (word-aligned). Target = 0x04 + 60 = 0x40.
    h(0x02, 0x4B0F)
    # 04: LDR r3, [r3]        → r3 = gBattleTypeFlags value
    h(0x04, 0x681B)
    # 06: MOVS r4, #8         → TRAINER bit mask
    h(0x06, 0x2408)
    # 08: TST r3, r4
    h(0x08, 0x4223)
    # 0A: BEQ +22 halfwords   → 0x38 (skip)
    h(0x0A, 0xD016)
    # 0C: LDRB r5, [r2, #0]  → next nickname char
    h(0x0C, 0x7815)
    # 0E: CMP r5, #0xFF
    h(0x0E, 0x2DFF)
    # 10: BNE +19 halfwords   → 0x38 (skip)
    h(0x10, 0xD113)
    # 12: MOV r3, r8          → r3 = dest_base  (high-reg MOV)
    h(0x12, 0x4643)
    # 14: ADDS r3, r3, r6     → r3 = dest_base + dest_idx
    h(0x14, 0x199B)
    # 16–35: write 8 bytes of " adverse"
    strb_hw = [0x701C, 0x705C, 0x709C, 0x70DC, 0x711C, 0x715C, 0x719C, 0x71DC]
    for i, (byte_val, strb) in enumerate(zip(_ADVERSE, strb_hw)):
        h(0x16 + i * 4,     0x2400 | byte_val)  # MOVS r4, #byte_val
        h(0x16 + i * 4 + 2, strb)               # STRB r4, [r3, #i]
    # 36: ADDS r6, #8         → advance dest_idx
    h(0x36, 0x2608)
    # 38: POP {r3, r4, r5}   ← BEQ / BNE target (skip lands here)
    h(0x38, 0xBC38)
    # 3A: LDR r3, [PC, #8]   → literal at cave+0x44 (outer_loop GBA addr)
    #     PC at 0x3A → word-aligned 0x3C. Target = 0x3C + 8 = 0x44.
    h(0x3A, 0x4B02)
    # 3C: BX r3
    h(0x3C, 0x4718)
    # 3E: NOP (word-align literal pool)
    h(0x3E, 0xBF00)
    # 40: gBattleTypeFlags address
    w(0x40, _FLAGS)
    # 44: outer_loop GBA address (Thumb bit set)
    w(0x44, outer_gba)

    return bytes(cave)


# Cave A: for 0xD7BB4 — outer loop at 0xD82AA (pixel-width already accumulated inline)
_CAVE_A_FILE = 0x1D89C
_CAVE_A = _make_cave(0xD82AA)

# Cave B: for other five sites — outer loop at 0xD82A4 (accumulates pixel-width)
_CAVE_B_FILE = 0x1D8E4  # = _CAVE_A_FILE + 72
_CAVE_B = _make_cave(0xD82A4)

assert len(_CAVE_A) == 72
assert len(_CAVE_B) == 72
assert _CAVE_B_FILE == _CAVE_A_FILE + len(_CAVE_A)


# ---------------------------------------------------------------------------
# Patch table
# ---------------------------------------------------------------------------

PATCHES: list[tuple[int, bytes, bytes]] = [
    # ── Empty the trainer-foe prefix "L'adversaire " at 0xA4C61A ────────────
    # Change first byte 0xC6 ('L') → 0xFF (terminator) so prefix copy writes nothing.
    (0xA4C61A, bytes([0xC6]), bytes([0xFF])),

    # ── Empty the no-space form "L'adversaire" at 0xA4C64C ──────────────────
    (0xA4C64C, bytes([0xC6]), bytes([0xFF])),

    # ── Code cave A (72 bytes at 0x1D89C, currently free space) ─────────────
    (0x1D89C, b"\xff" * 72, _CAVE_A),

    # ── Code cave B (72 bytes at 0x1D8E4, currently free space) ─────────────
    (0x1D8E4, b"\xff" * 72, _CAVE_B),

    # ── BL patches: replace "B outer_loop + 00 00" with "BL cave" ────────────
    # Each original instruction is 2-byte B + 2-byte 00 00 padding = 4 bytes,
    # exactly the size of a Thumb BL.
    (0xD7BB4, bytes([0x79, 0xE3, 0x00, 0x00]), _bl(0xD7BB4, _CAVE_A_FILE)),
    (0xD7C94, bytes([0x06, 0xE3, 0x00, 0x00]), _bl(0xD7C94, _CAVE_B_FILE)),
    (0xD7D08, bytes([0xCC, 0xE2, 0x00, 0x00]), _bl(0xD7D08, _CAVE_B_FILE)),
    (0xD7D7C, bytes([0x92, 0xE2, 0x00, 0x00]), _bl(0xD7D7C, _CAVE_B_FILE)),
    (0xD7DF0, bytes([0x58, 0xE2, 0x00, 0x00]), _bl(0xD7DF0, _CAVE_B_FILE)),
    (0xD7E64, bytes([0x1E, 0xE2, 0x00, 0x00]), _bl(0xD7E64, _CAVE_B_FILE)),
]


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def apply_patches(data: bytearray, patches: list = PATCHES) -> int:
    applied = 0
    for offset, old, new in patches:
        if len(old) != len(new):
            raise ValueError(f"0x{offset:X}: length mismatch")
        current = bytes(data[offset: offset + len(old)])
        if current == new:
            continue  # already patched
        if current != old:
            raise ValueError(
                f"0x{offset:X}: unexpected bytes {current.hex(' ')} "
                f"(expected {old.hex(' ')})"
            )
        data[offset: offset + len(new)] = new
        applied += 1
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    applied = apply_patches(data)
    if applied:
        args.rom.write_bytes(data)
    print(f"Battle-prefix patches applied: {applied} (of {len(PATCHES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
