#!/usr/bin/env python3
"""Patch battle-name display: trainer foe "L'adversaire X" → "X adverse",
wild Pokémon "sauvage X" → "X sauvage".

Root-cause fix: the old approach checked [r2]==0xFF inside the cave, but the
handler's own pixel_width guard already ensures [r2]!=0xFF at every BL site
(the BEQ that would skip the BL fires precisely when char==0xFF).  The cave
therefore never fired to write a suffix.

New design: each cave copies the COMPLETE nickname from [r2] to the text
buffer, appends the fixed 8-byte suffix, then writes 0xFF as a terminator.
The text renderer stops at the first 0xFF so whatever the outer loop and
Cave B2-B5 write afterward is invisible.

Two 108-byte Thumb code caves in free ROM space (0x1D89C / 0x1D908):

  Cave A (wild,    suffix " sauvage", target 0xD82AA) — patched at 0xD7BB4
  Cave B (trainer, suffix " adverse", target 0xD82A4) — patched at 0xD7C94

Cave B2-B5 (sites 0xD7D08/7C/F0/E64) are NOT patched; their original
"B outer_loop" code is retained and their output falls after our 0xFF
terminator, so it is harmless.

Cave structure (80 bytes of code + 28 bytes of 0xFF padding = 108 bytes):

  0x00  PUSH {r2, r4, r5}
  0x02  LDRB r4, [r2, #0]         ← copy_loop
  0x04  CMP  r4, #0xFF
  0x06  BEQ  → write_suffix (0x14)
  0x08  MOV  r5, r8               (dest_base)
  0x0A  ADDS r5, r5, r6           (dest ptr = dest_base + dest_idx)
  0x0C  STRB r4, [r5, #0]
  0x0E  ADDS r6, #1
  0x10  ADDS r2, #1
  0x12  B    → copy_loop (0x02)
  0x14  MOV  r5, r8               ← write_suffix
  0x16  ADDS r5, r5, r6
  0x18..0x37  8× (MOVS r4, #byte; STRB r4, [r5, #i])  ← suffix bytes
  0x38  ADDS r6, #8
  0x3A  MOV  r5, r8
  0x3C  ADDS r5, r5, r6
  0x3E  MOVS r4, #0xFF
  0x40  STRB r4, [r5, #0]         ← write terminator
  0x42  ADDS r6, #1
  0x44  POP  {r2, r4, r5}
  0x46  LDR  r3, [PC, #4]         → literal at 0x4C
  0x48  BX   r3
  0x4A  NOP
  0x4C  outer_loop GBA addr (Thumb, 4 bytes)
  0x50..0x6B  0xFF padding

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
# Register protocol at cave entry:
#   r0  — pixel-width accumulation (preserved; outer loop uses it)
#   r1  — pixel-width of current char (preserved; outer_loop_B uses it)
#   r2  — ptr to current nickname char (first char, always ≠ 0xFF)
#   r4  — scratch (saved/restored by PUSH/POP)
#   r5  — scratch (saved/restored by PUSH/POP)
#   r6  — dest_idx in output buffer (updated by cave: += name_len + 8 + 1)
#   r8  — dest base address (high register; read via MOV r5, r8)
#
# After POP r2 is restored to its entry value; the outer loop overwrites it
# immediately (MOV r2, sp at 0xD82AC, or LDRB r2,[r5] at 0xD8388).
#
# " adverse" in CFRU: 00=sp D5=a D8=d EA=v D9=e E6=r E7=s D9=e
# " sauvage" in CFRU: 00=sp E7=s D5=a E9=u EA=v D5=a DB=g D9=e

_ADVERSE = bytes([0x00, 0xD5, 0xD8, 0xEA, 0xD9, 0xE6, 0xE7, 0xD9])
_SAUVAGE = bytes([0x00, 0xE7, 0xD5, 0xE9, 0xEA, 0xD5, 0xDB, 0xD9])
_ROM_BASE = 0x08000000

# STRB r4, [r5, #i] encodings (r5 as dest-pointer base, r4 as source)
_STRB_R5 = [0x702C, 0x706C, 0x70AC, 0x70EC, 0x712C, 0x716C, 0x71AC, 0x71EC]


def _make_cave(suffix: bytes, outer_loop_file: int) -> bytes:
    """Build a 108-byte Thumb cave: copy nickname from [r2] + suffix + 0xFF."""
    assert len(suffix) == 8
    outer_gba = _ROM_BASE + outer_loop_file + 1  # +1 = Thumb interworking

    # Start with free-space fill so the patch check works on partial re-runs.
    cave = bytearray(b"\xff" * 108)

    def h(off: int, val: int) -> None:
        struct.pack_into("<H", cave, off, val)

    def w(off: int, val: int) -> None:
        struct.pack_into("<I", cave, off, val)

    # ── prologue ──────────────────────────────────────────────────────────────
    # 0x00: PUSH {r2, r4, r5}  (reglist = bit2|bit4|bit5 = 0x34)
    h(0x00, 0xB434)

    # ── copy_loop ─────────────────────────────────────────────────────────────
    # 0x02: LDRB r4, [r2, #0]   ← copy_loop_start
    h(0x02, 0x7814)
    # 0x04: CMP r4, #0xFF
    h(0x04, 0x2CFF)
    # 0x06: BEQ → write_suffix (0x14)
    #   PC = 0x0A, target = 0x14, imm8 = (0x14-0x0A)/2 = 5 = 0x05
    h(0x06, 0xD005)
    # 0x08: MOV r5, r8   (dest_base; high-reg MOV: Rd=r5, Rs=r8 → 0x4645)
    h(0x08, 0x4645)
    # 0x0A: ADDS r5, r5, r6   (dest ptr = dest_base + dest_idx)
    #   0001 100 110 101 101 = 0x19AD
    h(0x0A, 0x19AD)
    # 0x0C: STRB r4, [r5, #0]
    h(0x0C, 0x702C)
    # 0x0E: ADDS r6, #1
    h(0x0E, 0x3601)
    # 0x10: ADDS r2, #1   (advance nickname pointer)
    h(0x10, 0x3201)
    # 0x12: B → copy_loop_start (0x02)
    #   PC = 0x16, target = 0x02, byte_off = -0x14 = -20, half_off = -10
    #   Two's-complement 8-bit of -10 = 0xF6 → 0xE7F6
    h(0x12, 0xE7F6)

    # ── write_suffix ──────────────────────────────────────────────────────────
    # 0x14: MOV r5, r8   ← write_suffix (BEQ lands here)
    h(0x14, 0x4645)
    # 0x16: ADDS r5, r5, r6
    h(0x16, 0x19AD)
    # 0x18..0x37: 8× (MOVS r4, #byte; STRB r4, [r5, #i])
    for i, (byte_val, strb) in enumerate(zip(suffix, _STRB_R5)):
        h(0x18 + i * 4,     0x2400 | byte_val)   # MOVS r4, #byte_val
        h(0x18 + i * 4 + 2, strb)                 # STRB r4, [r5, #i]
    # 0x38: ADDS r6, #8
    h(0x38, 0x3608)

    # ── write terminator ──────────────────────────────────────────────────────
    # 0x3A: MOV r5, r8
    h(0x3A, 0x4645)
    # 0x3C: ADDS r5, r5, r6
    h(0x3C, 0x19AD)
    # 0x3E: MOVS r4, #0xFF
    h(0x3E, 0x24FF)
    # 0x40: STRB r4, [r5, #0]
    h(0x40, 0x702C)
    # 0x42: ADDS r6, #1
    h(0x42, 0x3601)

    # ── epilogue ──────────────────────────────────────────────────────────────
    # 0x44: POP {r2, r4, r5}
    h(0x44, 0xBC34)
    # 0x46: LDR r3, [PC, #4]  → literal at 0x4C
    #   PC_aligned = (0x46+4)&~3 = 0x48, N = 0x4C-0x48 = 4, word_off = 1
    h(0x46, 0x4B01)
    # 0x48: BX r3
    h(0x48, 0x4718)
    # 0x4A: NOP (word-align literal pool)
    h(0x4A, 0xBF00)
    # 0x4C: outer_loop GBA address (Thumb bit set)
    w(0x4C, outer_gba)
    # 0x50..0x6B: already filled with 0xFF (free-space padding)

    return bytes(cave)


# Cave A: wild battles — outer loop at 0xD82AA; patched at site 0xD7BB4
_CAVE_A_FILE = 0x1D89C
_CAVE_A = _make_cave(_SAUVAGE, 0xD82AA)

# Cave B: trainer battles — outer loop at 0xD82A4; patched at site 0xD7C94
_CAVE_B_FILE = 0x1D908   # = _CAVE_A_FILE + 108
_CAVE_B = _make_cave(_ADVERSE, 0xD82A4)

assert len(_CAVE_A) == 108
assert len(_CAVE_B) == 108
assert _CAVE_B_FILE == _CAVE_A_FILE + len(_CAVE_A)


# ---------------------------------------------------------------------------
# Patch table
# ---------------------------------------------------------------------------

PATCHES: list[tuple[int, bytes, bytes]] = [
    # ── Empty the wild Pokémon prefix "sauvage" at 0xA4C636 ─────────────────
    # Change first byte 0xE7 ('s') → 0xFF (terminator) so prefix copy writes nothing.
    (0xA4C636, bytes([0xE7]), bytes([0xFF])),

    # ── Empty the trainer-foe prefix "L'adversaire " at 0xA4C61A ────────────
    (0xA4C61A, bytes([0xC6]), bytes([0xFF])),

    # ── Empty the no-space form "L'adversaire" at 0xA4C64C ──────────────────
    (0xA4C64C, bytes([0xC6]), bytes([0xFF])),

    # ── Code cave A — wild battles (" sauvage" suffix) ───────────────────────
    (0x1D89C, b"\xff" * 108, _CAVE_A),

    # ── Code cave B — trainer battles (" adverse" suffix) ────────────────────
    (0x1D908, b"\xff" * 108, _CAVE_B),

    # ── BL patches: replace "B outer_loop + 00 00" with "BL cave" ─────────
    # Cave A site (token 0x0E — wild name):
    (0xD7BB4, bytes([0x79, 0xE3, 0x00, 0x00]), _bl(0xD7BB4, _CAVE_A_FILE)),
    # Cave B1 site (token 0x10 — trainer name, standard single battle):
    (0xD7C94, bytes([0x06, 0xE3, 0x00, 0x00]), _bl(0xD7C94, _CAVE_B_FILE)),
    # Cave B2-B5 (0xD7D08/7C/F0/E64) are NOT patched — their original
    # "B outer_loop" code is retained.  Any chars they write land after our
    # 0xFF terminator and are invisible to the text renderer.
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
            # Single-byte → 0xFF patches zero the first byte of a text prefix
            # so the engine's prefix-copy loop writes nothing.  The FR builder
            # may have already replaced the English text with a French
            # translation at this offset; we must zero it regardless.
            if len(old) == 1 and new == bytes([0xFF]):
                pass  # write 0xFF unconditionally
            else:
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
