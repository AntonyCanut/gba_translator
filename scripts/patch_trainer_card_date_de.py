#!/usr/bin/env python3
"""Render the Trainer Card start-of-adventure date in German order.

Port of ``patch_trainer_card_date_fr.py`` (see that file for the full
background). The English game builds the card date inline (the 44-byte
block at file 0x1ED8D76) as::

    StringCopy (dest, month_name)      ; "Jan."
    StringAppend(dest, day)            ; "Jan.19"
    StringAppend(dest, ", ")           ; "Jan.19, "
    StringAppend(dest, year)           ; "Jan.19, 2026"

i.e. *Month Day, Year* — American order, not the German *Day Month Year*.
None of it is reachable by the text pipeline (no FDnn date template exists),
and it cannot be reordered in place for the same register-pressure reason
documented in the FR script (r4/r5/r6/r7 pinned, StringCopy/StringAppend
clobber r0-r3).

This is the same free-space builder + veneer redirect as the FR port — the
assembled sequence (day + " " + month + " " + year) and every address it
touches (builder function table, month pointer table, dest/day/year buffers,
the inline block, the print continuation, the ``bx r3`` veneer) are engine
code shared by every language build, not FR-specific. Only the month-name
text differs, and that comes from whatever is already in ROM (English by
default, or German where ``patch_time_format_de.py`` has patched a cell) —
no language-specific logic lives in this script.

Result on screen: "19 Juli 2026" (once the corresponding month cell has been
translated by ``patch_time_format_de.py``; untranslated months fall back to
their English abbreviation, exactly as in the FR build).

Every write verifies the bytes it expects and is idempotent.

Usage:
    python3 scripts/patch_trainer_card_date_de.py --rom output/roms/GenedRom-de.gba
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

# ---- fixed addresses -------------------------------------------------------
BUILDER_FILE = 0x280120           # free space (verified 0xFF in the DE build)
BUILDER_GBA = 0x08000000 + BUILDER_FILE
STRING_COPY = 0x08008D84          # StringCopy(dest, src)
STRING_APPEND = 0x08008DA4        # StringAppend(dest, src)
MONTH_TABLE = 0x09FE6BF8          # table base (GBA); entry = *(base + month*4)
DEST = 0x02021D18                 # assembled date buffer
DAY = 0x02021CD0                  # 2-digit day (already converted by caller)
YEAR = 0x02021CF0                 # 4-digit year (already converted by caller)

BLOCK_FILE = 0x1ED8D76            # inline assembly block to overwrite (44 bytes)
BLOCK_LEN = 0x2C
PRINT_GBA = 0x08000000 + 0x1ED8DA2  # code right after the block
VENEER_BX_R3 = 0x09ED920C         # bx r3 veneer (register-indirect call)
DEST_POOL_FILE = 0x1ED8E74        # existing pool word holding 0x02021D18

MONTH_PTR_TABLE_FILE = 0x1FE6BFC  # 12 live month-name pointers (month 1..12)


# ---- tiny Thumb encoders ---------------------------------------------------
def _u16(v: int) -> bytes:
    return struct.pack("<H", v & 0xFFFF)


def bl(src_gba: int, dst_gba: int) -> bytes:
    """Encode a Thumb BL from src_gba to dst_gba (4 bytes)."""
    off = (dst_gba - (src_gba + 4)) & 0x7FFFFF  # 23-bit two's complement
    hi = (off >> 12) & 0x7FF
    lo = (off >> 1) & 0x7FF
    return _u16(0xF000 | hi) + _u16(0xF800 | lo)


def ldr_pc(rd: int, cur_gba: int, pool_gba: int) -> bytes:
    """Encode ldr rd,[pc,#imm]; pool_gba must be word-aligned & ahead."""
    base = (cur_gba + 4) & ~3
    imm = pool_gba - base
    assert 0 <= imm <= 1020 and imm % 4 == 0, (hex(cur_gba), hex(pool_gba), imm)
    return _u16(0x4800 | (rd << 8) | (imm >> 2))


# ---- builder assembly ------------------------------------------------------
def assemble_builder() -> bytes:
    """Emit the free-space date builder (Thumb). Returns its bytes."""
    CODE_LEN = 0x36  # 54 bytes of code (push..pop) — asserted at the end
    pool_off = CODE_LEN
    if pool_off % 4 != 0:
        pool_off += 2  # nop pad
    sp_off = pool_off          # SP_STR (" ") stored first, 2 bytes -> pad word
    ptbl_off = sp_off + 4
    pdest_off = ptbl_off + 4
    pday_off = pday = ptbl_off + 8
    pyear_off = ptbl_off + 12
    psp_off = ptbl_off + 16

    def A(off):  # gba address of a builder offset
        return BUILDER_GBA + off

    out = bytearray()

    def emit(off_expected, b):
        assert len(out) == off_expected, (hex(len(out)), hex(off_expected))
        out.extend(b)

    emit(0x00, _u16(0xB570))                      # push {r4,r5,r6,lr}
    emit(0x02, _u16(0x0080))                      # lsls r0,r0,#2
    emit(0x04, ldr_pc(1, A(0x04), A(ptbl_off)))   # ldr r1,=MONTH_TABLE
    emit(0x06, _u16(0x5844))                      # ldr r4,[r0,r1]
    emit(0x08, ldr_pc(5, A(0x08), A(pdest_off)))  # ldr r5,=DEST
    emit(0x0A, ldr_pc(6, A(0x0A), A(pday)))       # ldr r6,=DAY
    emit(0x0C, _u16(0x1C28))                      # adds r0,r5,#0
    emit(0x0E, _u16(0x1C31))                      # adds r1,r6,#0
    emit(0x10, bl(A(0x10), STRING_COPY))          # StringCopy(dest, day)
    emit(0x14, _u16(0x1C28))                      # adds r0,r5,#0
    emit(0x16, ldr_pc(1, A(0x16), A(psp_off)))    # ldr r1,=SP_STR
    emit(0x18, bl(A(0x18), STRING_APPEND))        # append " "
    emit(0x1C, _u16(0x1C28))                      # adds r0,r5,#0
    emit(0x1E, _u16(0x1C21))                      # adds r1,r4,#0  (month)
    emit(0x20, bl(A(0x20), STRING_APPEND))        # append month
    emit(0x24, _u16(0x1C28))                      # adds r0,r5,#0
    emit(0x26, ldr_pc(1, A(0x26), A(psp_off)))    # ldr r1,=SP_STR
    emit(0x28, bl(A(0x28), STRING_APPEND))        # append " "
    emit(0x2C, _u16(0x1C28))                      # adds r0,r5,#0
    emit(0x2E, ldr_pc(1, A(0x2E), A(pyear_off)))  # ldr r1,=YEAR
    emit(0x30, bl(A(0x30), STRING_APPEND))        # append year
    emit(0x34, _u16(0xBD70))                      # pop {r4,r5,r6,pc}

    assert len(out) == CODE_LEN, (hex(len(out)), hex(CODE_LEN))
    if len(out) % 4 != 0:
        out.extend(_u16(0x46C0))                  # nop (align)
    assert len(out) == sp_off
    out.extend(b"\x00\xff\xff\xff")               # SP_STR = " " + term (word pad)
    out.extend(struct.pack("<I", MONTH_TABLE))
    out.extend(struct.pack("<I", DEST))
    out.extend(struct.pack("<I", DAY))
    out.extend(struct.pack("<I", YEAR))
    out.extend(struct.pack("<I", A(sp_off)))      # &SP_STR
    return bytes(out)


def assemble_redirect() -> bytes:
    """Emit the 44-byte replacement for the inline block at 0x1ED8D76."""
    b0 = BLOCK_FILE + 0x08000000        # 0x09ED8D76
    out = bytearray()
    # ldr r7,[pc,#imm] -> existing pool 0x1ED8E74 (=0x02021D18) for the printer
    out += ldr_pc(7, b0 + 0x00, DEST_POOL_FILE + 0x08000000)   # 0x8d76
    out += _u16(0x9805)                 # 0x8d78 ldr r0,[sp,#0x14]  (month idx)
    out += ldr_pc(3, b0 + 0x04, b0 + 0x0E)  # 0x8d7a ldr r3,=builder|1 (pool @+0x0E)
    out += bl(b0 + 0x06, VENEER_BX_R3)  # 0x8d7c bl 0x9ED920C (bx r3)
    off = PRINT_GBA - ((b0 + 0x0A) + 4)  # 0x8d80 b 0x9ED8DA2
    out += _u16(0xE000 | ((off >> 1) & 0x7FF))
    out += _u16(0x46C0)                 # 0x8d82 nop (align pool to +0x0E? -> 0x8d84)
    # pool word (builder thumb address) at file 0x8d84 == b0+0x0E
    assert len(out) == 0x0E
    out += struct.pack("<I", BUILDER_GBA | 1)   # 0x8d84..0x8d87
    while len(out) < BLOCK_LEN:          # nop fill to 44 bytes (unreached)
        out += _u16(0x46C0)
    assert len(out) == BLOCK_LEN, len(out)
    return bytes(out)


def _string_end(data: bytes, gba_ptr: int) -> int:
    """File offset of the 0xFF terminating the string at gba_ptr."""
    off = gba_ptr - 0x08000000
    i = off
    while data[i] != 0xFF:
        i += 1
    return i


def apply(data: bytearray) -> int:
    changed = 0
    builder = assemble_builder()
    redirect = assemble_redirect()

    # 1) builder into free space
    cur = bytes(data[BUILDER_FILE:BUILDER_FILE + len(builder)])
    if cur == builder:
        pass
    elif cur == b"\xff" * len(builder):
        data[BUILDER_FILE:BUILDER_FILE + len(builder)] = builder
        changed += 1
    else:
        raise ValueError(f"builder slot 0x{BUILDER_FILE:X} not free: {cur.hex()}")

    # 2) redirect the inline block
    cur = bytes(data[BLOCK_FILE:BLOCK_FILE + BLOCK_LEN])
    if cur == redirect:
        pass
    else:
        # original English/DE block starts with 05 9b 3e 4f ... (ldr r3,[sp,#20])
        if cur[:2] != b"\x05\x9b":
            raise ValueError(f"block 0x{BLOCK_FILE:X} unexpected: {cur.hex()}")
        data[BLOCK_FILE:BLOCK_FILE + BLOCK_LEN] = redirect
        changed += 1

    # 3) trim trailing space from month cells (avoid double space)
    for k in range(12):
        ptr = struct.unpack("<I", data[MONTH_PTR_TABLE_FILE + 4 * k:
                                       MONTH_PTR_TABLE_FILE + 4 * k + 4])[0]
        end = _string_end(data, ptr)
        if end > 0 and data[end - 1] == 0x00:   # trailing SPACE byte
            data[end - 1] = 0xFF                 # move terminator back one
            changed += 1
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-de.gba"))
    args = ap.parse_args()
    data = bytearray(args.rom.read_bytes())
    n = apply(data)
    if n:
        args.rom.write_bytes(data)
    print(f"Trainer-card date patches applied: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
