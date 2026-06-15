#!/usr/bin/env python3
"""Patch battle-name display so the French descriptor follows the Pokémon name:
trainer foe "L'adversaire X" -> "X adverse", wild "sauvage X" -> "X sauvage".

Root cause of the previous failures
------------------------------------
The battle-string expansion routine builds the *final* displayed string inline:
it copies the foe descriptor prefix, then the name, then keeps reading the
message template ("... de Vitesse fortement augmente !") straight after, with
NO 0xFF terminator in between.  Two earlier cave designs both broke on this:

  * "copy [r2] + suffix + 0xFF"  -> the 0xFF terminator truncated the rest of
    the message (everything after the suffix vanished).
  * "write suffix only, movs r6,#8, re-enter loop" -> guarded on [r2]==0xFF
    (which never happens for a real name, so the suffix was never written) and
    clobbered the destination index with an absolute `movs r6,#8`.

Correct design (this file)
--------------------------
Each foe-name site (wild 0xD7BB4, trainer 0xD7C94) is a `B outer_loop`
that, in the stock engine, formats the name into the stack buffer at [sp] and
copies it to the display buffer.  We empty the prefix string so no prefix is
printed, then redirect that branch to a self-contained cave that:

  1. copies the foe name from [r2] into the display buffer (r8 + r6),
  2. appends the fixed 8-byte suffix INLINE (no 0xFF terminator),
  3. writes 0xFF to the engine's name buffer at [sp] so the engine's own
     name copy becomes a no-op,
  4. jumps to 0x80D82E4 -- the convergence point *after* name formatting --
     which then performs the (now empty) name copy, the gender-symbol handling
     and continues expanding the rest of the message template normally.

Result: the display buffer receives "<name><suffix>" followed by the untouched
remainder of the message.  No truncation, no double name, no flag/scratch RAM.

Register protocol at each branch site (stock engine, verified by disassembly):
  r2  -> pointer to the foe name buffer (0x02023D6B); its first byte is read by
         the engine's font-width code right before the branch, so it is the
         string about to be rendered (never 0xFF).
  r6  -> current write index into the display buffer (updated by the cave).
  r8  -> display buffer base (high register, read via MOV r5, r8).
  sp  -> base of the engine's temporary name buffer.
  r0/r1/r3 -> scratch reloaded by the engine after 0x80D82E4; r4/r5 are
         preserved by the cave's PUSH/POP.

" adverse" in CFRU: 00=sp D5=a D8=d EA=v D9=e E6=r E7=s D9=e
" sauvage" in CFRU: 00=sp E7=s D5=a E9=u EA=v D5=a DB=g D9=e

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
        raise ValueError(f"BL out of range: 0x{site:X} -> 0x{target:X}")
    imm_hi = (offset >> 12) & 0x7FF
    imm_lo = (offset >> 1) & 0x7FF
    return struct.pack("<HH", 0xF000 | imm_hi, 0xF800 | imm_lo)


# ---------------------------------------------------------------------------
# Code cave builder
# ---------------------------------------------------------------------------
#
# " adverse" / " sauvage" CFRU byte sequences (8 bytes each, leading space).
_ADVERSE = bytes([0x00, 0xD5, 0xD8, 0xEA, 0xD9, 0xE6, 0xE7, 0xD9])
_SAUVAGE = bytes([0x00, 0xE7, 0xD5, 0xE9, 0xEA, 0xD5, 0xDB, 0xD9])
_ROM_BASE = 0x08000000

# Convergence point reached after the stock name formatting: it does the (now
# empty) name copy, gender handling, and continues the message template.
_CONVERGE_FILE = 0xD82E4

# STRB r4, [r5, #i] encodings (r5 = dest pointer, r4 = source byte), i = 0..7.
_STRB_R5 = [0x702C, 0x706C, 0x70AC, 0x70EC, 0x712C, 0x716C, 0x71AC, 0x71EC]

_CAVE_LEN = 108


def _make_cave(suffix: bytes) -> bytes:
    """Build a Thumb cave: copy name from [r2] + suffix (inline, no terminator),
    blank the engine name buffer at [sp], then jump to the convergence point."""
    assert len(suffix) == 8
    converge_gba = _ROM_BASE + _CONVERGE_FILE + 1  # +1 = Thumb interworking

    cave = bytearray(b"\xff" * _CAVE_LEN)

    def h(off: int, val: int) -> None:
        struct.pack_into("<H", cave, off, val)

    def w(off: int, val: int) -> None:
        struct.pack_into("<I", cave, off, val)

    # -- prologue ------------------------------------------------------------
    # 0x00: PUSH {r4, r5}  (reglist bit4|bit5 = 0x30); SP -= 8.
    h(0x00, 0xB430)

    # -- copy_loop: copy foe name from [r2] into display buffer (r8 + r6) -----
    # 0x02: LDRB r4, [r2, #0]
    h(0x02, 0x7814)
    # 0x04: CMP r4, #0xFF
    h(0x04, 0x2CFF)
    # 0x06: BEQ -> write_suffix (0x14); PC=0x0A, imm8=(0x14-0x0A)/2=5
    h(0x06, 0xD005)
    # 0x08: MOV r5, r8
    h(0x08, 0x4645)
    # 0x0A: ADDS r5, r5, r6
    h(0x0A, 0x19AD)
    # 0x0C: STRB r4, [r5, #0]
    h(0x0C, 0x702C)
    # 0x0E: ADDS r6, #1
    h(0x0E, 0x3601)
    # 0x10: ADDS r2, #1
    h(0x10, 0x3201)
    # 0x12: B -> copy_loop (0x02); PC=0x16, byte_off=-0x14 -> 0xE7F6
    h(0x12, 0xE7F6)

    # -- write_suffix: append the 8 suffix bytes inline (no terminator) -------
    # 0x14: MOV r5, r8
    h(0x14, 0x4645)
    # 0x16: ADDS r5, r5, r6
    h(0x16, 0x19AD)
    # 0x18..0x37: 8x (MOVS r4, #byte; STRB r4, [r5, #i])
    for i, (byte_val, strb) in enumerate(zip(suffix, _STRB_R5)):
        h(0x18 + i * 4,     0x2400 | byte_val)   # MOVS r4, #byte_val
        h(0x18 + i * 4 + 2, strb)                # STRB r4, [r5, #i]
    # 0x38: ADDS r6, #8  (advance display index past the suffix)
    h(0x38, 0x3608)

    # -- blank the engine name buffer at [sp] so its own name copy is a no-op -
    # 0x3A: ADD r5, sp, #8  (orig SP = current SP + 8 bytes pushed)
    h(0x3A, 0xAD02)
    # 0x3C: MOVS r4, #0xFF
    h(0x3C, 0x24FF)
    # 0x3E: STRB r4, [r5, #0]
    h(0x3E, 0x702C)

    # -- epilogue: restore scratch and jump to the convergence point ---------
    # 0x40: POP {r4, r5}  (SP += 8, back to function frame)
    h(0x40, 0xBC30)
    # 0x42: LDR r3, [PC, #4]  -> literal at 0x48
    h(0x42, 0x4B01)
    # 0x44: BX r3
    h(0x44, 0x4718)
    # 0x46: NOP (word-align literal pool)
    h(0x46, 0xBF00)
    # 0x48: convergence GBA address (Thumb bit set)
    w(0x48, converge_gba)
    # 0x4C..: already filled with 0xFF (free-space padding)

    return bytes(cave)


# Cave A: wild battles (" sauvage" suffix); patched at site 0xD7BB4.
_CAVE_A_FILE = 0x1D89C
_CAVE_A = _make_cave(_SAUVAGE)

# Cave B: trainer battles (" adverse" suffix); patched at site 0xD7C94.
_CAVE_B_FILE = 0x1D908   # = _CAVE_A_FILE + 108
_CAVE_B = _make_cave(_ADVERSE)

assert len(_CAVE_A) == _CAVE_LEN
assert len(_CAVE_B) == _CAVE_LEN
assert _CAVE_B_FILE == _CAVE_A_FILE + len(_CAVE_A)


# ---------------------------------------------------------------------------
# Patch table
# ---------------------------------------------------------------------------

PATCHES: list[tuple[int, bytes, bytes]] = [
    # -- Empty the wild Pokémon prefix "sauvage" at 0xA4C636 -----------------
    # First byte 0xE7 ('s') -> 0xFF so the engine's prefix-copy loop is skipped.
    (0xA4C636, bytes([0xE7]), bytes([0xFF])),

    # -- Empty the trainer-foe prefix "L'adversaire " at 0xA4C61A -----------
    (0xA4C61A, bytes([0xC6]), bytes([0xFF])),

    # -- Empty the no-space form "L'adversaire" at 0xA4C64C -----------------
    (0xA4C64C, bytes([0xC6]), bytes([0xFF])),

    # -- Code cave A -- wild battles (" sauvage" suffix) --------------------
    (_CAVE_A_FILE, b"\xff" * _CAVE_LEN, _CAVE_A),

    # -- Code cave B -- trainer battles (" adverse" suffix) ----------------
    (_CAVE_B_FILE, b"\xff" * _CAVE_LEN, _CAVE_B),

    # -- BL patches: replace "B outer_loop + 00 00" with "BL cave" ---------
    # Cave A site (wild foe name):
    (0xD7BB4, bytes([0x79, 0xE3, 0x00, 0x00]), _bl(0xD7BB4, _CAVE_A_FILE)),
    # Cave B site (trainer foe name, standard single battle):
    (0xD7C94, bytes([0x06, 0xE3, 0x00, 0x00]), _bl(0xD7C94, _CAVE_B_FILE)),
    # NOTE: the multi-battle foe-name variants (0xD7D08/7C/F0/E64) route to a
    # different formatting tail and still print only the bare name (no suffix);
    # they are left untouched here and tracked as a follow-up.
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
