#!/usr/bin/env python3
"""Patch battle-name display: trainer foe "L'adversaire X" → "X adverse",
wild Pokémon "sauvage X" → "X sauvage".

The CFRU battle engine always writes NAME_WITH_PREFIX as prefix+nickname.  To
reverse the order we use two 108-byte Thumb code caves in free ROM space
(0x1D89C / 0x1D908).  Each cave is called via BL from the six per-character
exit points of the NAME_WITH_PREFIX handler:

  Cave A (target 0xD82AA) — used by 0xD7BB4
  Cave B (target 0xD82A4) — used by 0xD7C94 / 0xD7D08 / 0xD7D7C / 0xD7DF0 / 0xD7E64

Cave structure (108 bytes):
  1. PUSH {r3,r4,r5}
  2. Load gBattleTypeFlags (0x02022B4C) into r3; MOVS r4, #8 (trainer mask)
  3. LDRB r5, [r2, #0]: read NEXT nickname char; CMP r5, #0xFF
  4. BNE → skip: not last char → jump to LDR/BX outer_loop (no POP)
  5. MOV r5, r8; ADDS r5, r5, r6: compute dest ptr = dest_base + dest_idx
  6. TST r3, r4: test trainer bit
  7. BEQ → wild block (trainer bit = 0)
  8. [trainer] Write " adverse" (00 D5 D8 EA D9 E6 E7 D9) to [r5]; MOVS r6,#8; B pop
  9. [wild]    Write " sauvage" (00 E7 D5 E9 EA D5 DB D9) to [r5]; MOVS r6,#8
 10. POP {r3,r4,r5}; LDR r3, outer_loop_addr; BX r3

The "L'adversaire " prefix strings at 0xA4C61A / 0xA4C64C and the "sauvage"
prefix at 0xA4C636 are emptied by changing their first byte to 0xFF so the
engine's prefix-copy loop writes nothing.

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
#   r3-r5 — scratch (saved/restored by cave PUSH/POP on the write path)
#   r6  — dest_idx in output buffer (set to 8 after suffix appended)
#   r8  — dest base address (high register; read-only in cave)
#
# " adverse" in CFRU: 00=sp D5=a D8=d EA=v D9=e E6=r E7=s D9=e
# " sauvage" in CFRU: 00=sp E7=s D5=a E9=u EA=v D5=a DB=g D9=e

_ADVERSE = bytes([0x00, 0xD5, 0xD8, 0xEA, 0xD9, 0xE6, 0xE7, 0xD9])
_SAUVAGE = bytes([0x00, 0xE7, 0xD5, 0xE9, 0xEA, 0xD5, 0xDB, 0xD9])
_FLAGS    = 0x02022B4C   # gBattleTypeFlags (GBA RAM)
_ROM_BASE = 0x08000000

# STRB r4, [r5, #i] encodings (r5 as dest-pointer base)
_STRB_R5 = [0x702C, 0x706C, 0x70AC, 0x70EC, 0x712C, 0x716C, 0x71AC, 0x71EC]


def _make_cave(outer_loop_file: int) -> bytes:
    """Build a 108-byte Thumb cave that handles both trainer and wild suffixes."""
    outer_gba = _ROM_BASE + outer_loop_file + 1  # +1 = Thumb interworking

    cave = bytearray(108)

    def h(off: int, val: int) -> None:
        struct.pack_into("<H", cave, off, val)

    def w(off: int, val: int) -> None:
        struct.pack_into("<I", cave, off, val)

    # 00: PUSH {r3, r4, r5}
    h(0x00, 0xB438)
    # 02: LDR r3, [PC, #0x60]  → literal at cave+0x64 (_FLAGS addr)
    #     PC at 0x02 word-aligned: word_align(0x02+4) = 0x04.
    #     Target = cave+0x64.  Offset = 0x64-0x04 = 0x60.  Word offset = 24 = 0x18.
    h(0x02, 0x4B18)
    # 04: LDR r3, [r3]          → r3 = gBattleTypeFlags value
    h(0x04, 0x681B)
    # 06: MOVS r4, #8           → TRAINER bit mask
    h(0x06, 0x2408)
    # 08: LDRB r5, [r2, #0]    → next nickname char (last char = 0xFF)
    h(0x08, 0x7815)
    # 0A: CMP r5, #0xFF
    h(0x0A, 0x2DFF)
    # 0C: BNE +0x4E → 0x5E (skip: not last char — jump straight to LDR/BX)
    #     PC = 0x10, target = 0x5E, byte_off = 0x4E = 78, half_off = 39 = 0x27.
    h(0x0C, 0xD127)
    # 0E: MOV r5, r8            → r5 = dest_base  (r5 reused: last-char check done)
    #     High-reg MOV: Rd=r5(D=0,Rdn=101), Rm=r8(1000) → 0x4645
    h(0x0E, 0x4645)
    # 10: ADDS r5, r5, r6       → r5 = dest_base + dest_idx
    #     ADDS Rd,Rn,Rm: 0001 100 110 101 101 = 0x19AD
    h(0x10, 0x19AD)
    # 12: TST r3, r4            → test trainer bit (r3=flags, r4=8)
    h(0x12, 0x4223)
    # 14: BEQ +0x22 → 0x3A (wild block: trainer bit = 0)
    #     PC = 0x18, target = 0x3A, byte_off = 0x22 = 34, half_off = 17 = 0x11.
    h(0x14, 0xD011)

    # 16–35: TRAINER — write " adverse" at [r5]
    for i, (byte_val, strb) in enumerate(zip(_ADVERSE, _STRB_R5)):
        h(0x16 + i * 4,     0x2400 | byte_val)   # MOVS r4, #byte_val
        h(0x16 + i * 4 + 2, strb)                 # STRB r4, [r5, #i]

    # 36: MOVS r6, #8  (matches original verified-working encoding)
    h(0x36, 0x2608)
    # 38: B +0x20 → 0x5C (POP)
    #     PC = 0x3C, target = 0x5C, byte_off = 0x20 = 32, half_off = 16 = 0x10.
    h(0x38, 0xE010)

    # 3A–59: WILD — write " sauvage" at [r5]  (← BEQ→wild lands here)
    for i, (byte_val, strb) in enumerate(zip(_SAUVAGE, _STRB_R5)):
        h(0x3A + i * 4,     0x2400 | byte_val)   # MOVS r4, #byte_val
        h(0x3A + i * 4 + 2, strb)                 # STRB r4, [r5, #i]

    # 5A: MOVS r6, #8
    h(0x5A, 0x2608)
    # 5C: POP {r3, r4, r5}  (← B→pop lands here; also wild block falls through)
    h(0x5C, 0xBC38)
    # 5E: LDR r3, [PC, #8]  → literal at cave+0x68  (← BNE→skip lands here)
    #     PC at 0x5E word-aligned: word_align(0x5E+4) = 0x60.
    #     Target = cave+0x68.  Offset = 0x08.  Word offset = 2.
    h(0x5E, 0x4B02)
    # 60: BX r3
    h(0x60, 0x4718)
    # 62: NOP (word-align literal pool)
    h(0x62, 0xBF00)
    # 64: gBattleTypeFlags address
    w(0x64, _FLAGS)
    # 68: outer_loop GBA address (Thumb bit set)
    w(0x68, outer_gba)

    return bytes(cave)


# Cave A: for 0xD7BB4 — outer loop at 0xD82AA (pixel-width already accumulated inline)
_CAVE_A_FILE = 0x1D89C
_CAVE_A = _make_cave(0xD82AA)

# Cave B: for other five sites — outer loop at 0xD82A4 (accumulates pixel-width)
_CAVE_B_FILE = 0x1D908   # = _CAVE_A_FILE + 108
_CAVE_B = _make_cave(0xD82A4)

assert len(_CAVE_A) == 108
assert len(_CAVE_B) == 108
assert _CAVE_B_FILE == _CAVE_A_FILE + len(_CAVE_A)


# ---------------------------------------------------------------------------
# Patch table
# ---------------------------------------------------------------------------

PATCHES: list[tuple[int, bytes, bytes]] = [
    # ── Empty the wild Pokémon prefix "sauvage" at 0xA4C636 ─────────────────
    # Change first byte 0xE7 ('s') → 0xFF (terminator) so prefix copy writes nothing.
    # The code cave appends " sauvage" AFTER the nickname instead.
    (0xA4C636, bytes([0xE7]), bytes([0xFF])),

    # ── Empty the trainer-foe prefix "L'adversaire " at 0xA4C61A ────────────
    # Change first byte 0xC6 ('L') → 0xFF (terminator).
    (0xA4C61A, bytes([0xC6]), bytes([0xFF])),

    # ── Empty the no-space form "L'adversaire" at 0xA4C64C ──────────────────
    (0xA4C64C, bytes([0xC6]), bytes([0xFF])),

    # ── Code cave A (108 bytes at 0x1D89C, currently free space) ─────────────
    (0x1D89C, b"\xff" * 108, _CAVE_A),

    # ── Code cave B (108 bytes at 0x1D908, currently free space) ─────────────
    (0x1D908, b"\xff" * 108, _CAVE_B),

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
