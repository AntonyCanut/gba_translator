#!/usr/bin/env python3
"""Composer le titre français de l’écran de surnom.

FireRed assemble nativement ``nom d’espèce + titre``. Cette routine remplace
uniquement ``DrawMonTextEntryBox`` afin de produire
``titre + nom d’espèce + espace + ?`` dans le build français.
"""

from __future__ import annotations

import argparse
import shutil
import struct
from pathlib import Path


ROM_BASE = 0x08000000
ROUTINE_FILE = 0x9F4F0
ROUTINE_GBA = ROM_BASE + ROUTINE_FILE
ROUTINE_SIZE = 0x7C

STRING_COPY = 0x08008D84
FILL_WINDOW_PIXEL_BUFFER = 0x0800445C
ADD_TEXT_PRINTER_PARAMETERIZED = 0x08002C48
PUT_WINDOW_TILEMAP = 0x08003FA0

NAMING_SCREEN_PTR = 0x0203998C
TEMPLATE_OFFSET = 0x1E28
WINDOW_OFFSET = 0x1E14
SPECIES_NAMES = 0x0966A98C

ORIGINAL_ROUTINE = bytes.fromhex(
    "30b58bb0184d28681849401801880b2041431748091803a869f73cfc28681549"
    "40180068816803a80f2269f767fc2868114c00190078112164f798ff28680019"
    "007801210091002101910291012103aa012363f781fb28680019007864f728fd"
    "0bb030bc01bc00478c990302341e00008ca96609281e0000141e0000"
)


def _bl(site: int, target: int) -> bytes:
    """Encoder un appel Thumb BL entre deux adresses GBA."""
    offset = target - (site + 4)
    if not (-0x400000 <= offset < 0x400000):
        raise ValueError(f"BL hors portée : 0x{site:X} → 0x{target:X}")
    return struct.pack(
        "<HH",
        0xF000 | ((offset >> 12) & 0x7FF),
        0xF800 | ((offset >> 1) & 0x7FF),
    )


def assemble_routine() -> bytes:
    """Assembler la routine Thumb de composition et de rendu du titre."""
    code = bytearray()

    def halfword(value: int) -> None:
        code.extend(struct.pack("<H", value))

    def call(target: int) -> None:
        site = ROUTINE_GBA + len(code)
        code.extend(_bl(site, target))

    halfword(0xB530)  # push {r4, r5, lr}
    halfword(0xB08B)  # sub sp, #0x2c
    halfword(0x4D1A)  # ldr r5, [pc, #0x68] -> sNamingScreen
    halfword(0x6828)  # ldr r0, [r5]
    halfword(0x491A)  # ldr r1, [pc, #0x68] -> template offset
    halfword(0x1840)  # adds r0, r0, r1
    halfword(0x6800)  # ldr r0, [r0]
    halfword(0x6881)  # ldr r1, [r0, #8] -> title
    halfword(0xA803)  # add r0, sp, #12 -> output buffer
    call(STRING_COPY)  # StringCopy(buffer, "Surnom de<0x00>")
    halfword(0x1C04)  # adds r4, r0, #0 -> output terminator

    halfword(0x6828)  # ldr r0, [r5]
    halfword(0x4916)  # ldr r1, [pc, #0x58] -> template offset
    halfword(0x1840)  # adds r0, r0, r1
    halfword(0x8981)  # ldrh r1, [r0, #12] -> species
    halfword(0x200B)  # movs r0, #11 -> species-name stride
    halfword(0x4341)  # muls r1, r0, r1
    halfword(0x4814)  # ldr r0, [pc, #0x50] -> species table
    halfword(0x1809)  # adds r1, r1, r0
    halfword(0x1C20)  # adds r0, r4, #0
    call(STRING_COPY)  # StringCopy(end, species name)

    halfword(0x21AC)  # movs r1, #'?'
    halfword(0x0209)  # lsls r1, r1, #8 -> bytes 00 AC
    halfword(0x8001)  # strh r1, [r0] -> " ?"
    halfword(0x21FF)  # movs r1, #0xff
    halfword(0x7081)  # strb r1, [r0, #2]

    halfword(0x6828)  # ldr r0, [r5]
    halfword(0x4C0E)  # ldr r4, [pc, #0x38] -> template offset
    halfword(0x3C14)  # subs r4, #0x14 -> window offset
    halfword(0x1900)  # adds r0, r0, r4
    halfword(0x7800)  # ldrb r0, [r0]
    halfword(0x2111)  # movs r1, #0x11
    call(FILL_WINDOW_PIXEL_BUFFER)

    halfword(0x6828)  # ldr r0, [r5]
    halfword(0x1900)  # adds r0, r0, r4
    halfword(0x7800)  # ldrb r0, [r0]
    halfword(0x2101)  # movs r1, #1
    halfword(0x9100)  # str r1, [sp]
    halfword(0x2100)  # movs r1, #0
    halfword(0x9101)  # str r1, [sp, #4]
    halfword(0x9102)  # str r1, [sp, #8]
    halfword(0x2101)  # movs r1, #1
    halfword(0xAA03)  # add r2, sp, #12
    halfword(0x2301)  # movs r3, #1
    call(ADD_TEXT_PRINTER_PARAMETERIZED)

    halfword(0x6828)  # ldr r0, [r5]
    halfword(0x1900)  # adds r0, r0, r4
    halfword(0x7800)  # ldrb r0, [r0]
    call(PUT_WINDOW_TILEMAP)
    halfword(0xB00B)  # add sp, #0x2c
    halfword(0xBD30)  # pop {r4, r5, pc}

    code.extend(struct.pack("<III", NAMING_SCREEN_PTR, TEMPLATE_OFFSET, SPECIES_NAMES))
    if len(code) != ROUTINE_SIZE:
        raise AssertionError(f"taille routine inattendue : {len(code)}")
    return bytes(code)


PATCHED_ROUTINE = assemble_routine()


def apply_patches(data: bytearray) -> int:
    """Appliquer le patch byte-exact, de façon idempotente."""
    current = bytes(data[ROUTINE_FILE:ROUTINE_FILE + ROUTINE_SIZE])
    if current == PATCHED_ROUTINE:
        return 0
    if current != ORIGINAL_ROUTINE:
        raise ValueError(
            f"0x{ROUTINE_FILE:X}: routine inattendue {current[:16].hex(' ')}"
        )
    data[ROUTINE_FILE:ROUTINE_FILE + ROUTINE_SIZE] = PATCHED_ROUTINE
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    applied = apply_patches(data)
    if applied:
        backup = args.rom.with_suffix(args.rom.suffix + ".bak")
        shutil.copy2(args.rom, backup)
        args.rom.write_bytes(data)
    print(f"Nickname-prompt patches applied: {applied} (of 1)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
