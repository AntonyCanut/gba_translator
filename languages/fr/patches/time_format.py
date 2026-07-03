#!/usr/bin/env python3
"""Switch the in-game date/time displays to French conventions.

The English game renders timestamps as "YYYY/MM/DD h:mm AM" (save
screen), "Sat. h:mm PM" (start-menu clock) and "h:mm AM - h:mm PM"
(scripted opening hours), converting the 23-hour RTC value to 12-hour
with an AM/PM suffix in code. None of that is reachable by the text
pipeline, so this post-build step patches the built ROM directly:

- save screen: 12-hour conversion branch forced unconditional (24 h),
  hour rendered with leading zeros, format template rewritten in place
  to "DD/MM/YYYY HH:MM" (AM/PM token dropped);
- start-menu clock: hour 0->12 and -12 conversions disabled (24 h),
  leading-zero hour, template rewritten to "Jjj. HH:MM", the seven
  weekday cells translated (Dim/Lun/Mar/Mer/Jeu/Ven/Sam);
- scripted time ranges: both 12-hour conversions disabled, the " AM" /
  " PM" suffix strings emptied;
- month-abbreviation cells translated in place (iso-length: Janv.,
  Fevr., Mars, Avr., Mai, Juil., Aout, Sept., Dec.).
- bag menu "Use" label repointed to "Utiliser" (string too long for
  in-place replacement; written into free space at 0x284EAB, all six
  pointer entries updated).
- dialogue speaker "Mom" label repointed to "Maman" (string too long
  for in-place replacement; written into free space at 0x284EBC, all
  five pointer entries updated).

Every patch verifies the bytes it expects (English original) and is
idempotent (already-patched cells are skipped).

Usage:
    python3 languages/fr/patches/time_format.py --rom output/roms/GenedRom-fr.gba
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import CHAR_TO_BYTE


def encode(text: str) -> bytes:
    return bytes(CHAR_TO_BYTE[c] for c in text)


def _cells(*names: str) -> bytes:
    return b"".join(encode(n) + b"\xff" for n in names)


def _slot(old_text: bytes, new_text: bytes) -> tuple[bytes, bytes]:
    """Pad new_text with 0xFF so it overwrites the whole old slot."""
    if len(new_text) > len(old_text):
        raise ValueError("replacement longer than original slot")
    return old_text, new_text + b"\xff" * (len(old_text) - len(new_text))

FD = lambda n: bytes((0xFD, n))  # buffer token  # noqa: E731
FC = lambda a, b: bytes((0xFC, a, b))  # format code  # noqa: E731
SLASH, DOT, COLON, SPACE = b"\xba", b"\xad", b"\xf0", b"\x00"

# Save-screen region 0x1F11DAC-0x1F11DCF holds "{COLOR}{SHADOW}Never" then
# the date template "{COLOR}{SHADOW}Y/M/D h:mm ampm". "Jamais" is one byte
# longer than "Never", but the French template (no AM/PM token) is three
# bytes shorter, so the region is re-laid-out as a whole: Jamais ends at
# 0x1F11DB8, the D/M/Y HH:MM template starts at 0x1F11DB9, and the
# template's single pointer (in the 0x1EB6260 literal pool slot) follows.
SAVE_TEMPLATE_OLD = (
    FC(0x01, 0x02) + FC(0x03, 0x03)
    + FD(0x02) + SLASH + FD(0x03) + SLASH + FD(0x04)
    + SPACE + FD(0x07) + COLON + FD(0x08) + SPACE + FD(0x0A) + b"\xff"
)
SAVE_TEMPLATE_NEW = (
    FC(0x01, 0x02) + FC(0x03, 0x03)
    + FD(0x04) + SLASH + FD(0x03) + SLASH + FD(0x02)
    + SPACE + FD(0x07) + COLON + FD(0x08) + b"\xff"
)

# Start-menu clock template: "Www. h:mm ampm" -> "Jjj. HH:MM"
CLOCK_TEMPLATE_OLD = (
    FD(0x0C) + DOT + SPACE + FD(0x02) + COLON + FD(0x03)
    + SPACE + FD(0x04) + b"\xff"
)
CLOCK_TEMPLATE_NEW = FD(0x0C) + DOT + SPACE + FD(0x02) + COLON + FD(0x03) + b"\xff"

# (offset, expected bytes, replacement bytes) — same length, byte-exact.
PATCHES = [
    # --- save screen (function at 0x1EB5EEC) ---
    # cmp r3,#0xc ; bls -> b : skip the "hour -= 12" path entirely
    (0x1EB5F12, b"\x04\xd9", b"\x04\xe0"),
    # hour ConvertIntToDecimalStringN mode: movs r2,r5 (0) -> movs r2,#2
    (0x1EB614C, b"\x2a\x00", b"\x02\x22"),
    # "Never" + date template region (see comment above)
    (0x1F11DAC, *_slot(
        FC(0x01, 0x02) + FC(0x03, 0x03) + encode("Never") + b"\xff"
        + SAVE_TEMPLATE_OLD,
        FC(0x01, 0x02) + FC(0x03, 0x03) + encode("Jamais") + b"\xff"
        + SAVE_TEMPLATE_NEW,
    )),
    # template pointer 0x09F11DB8 -> 0x09F11DB9 in the literal pool
    (0x1EB6260, b"\xb8\x1d\xf1\x09", b"\xb9\x1d\xf1\x09"),
    # --- start-menu clock (function at 0xA0B51C) ---
    # beq taken when hour==0 (display 12) -> nop: keep 0
    (0xA0B52E, b"\x03\xd0", b"\xc0\x46"),
    # cmp r3,#0xc ; bls -> b : skip "hour -= 12"
    (0xA0B534, b"\x00\xd9", b"\x00\xe0"),
    # hour mode: movs r2,#1 -> movs r2,#2 (leading zeros)
    (0xA0B53C, b"\x01\x22", b"\x02\x22"),
    (0xA4E533, *_slot(CLOCK_TEMPLATE_OLD, CLOCK_TEMPLATE_NEW)),
    # weekday cells (4 bytes each, referenced by the table at 0xA6D0AC)
    (0xA4E554, _cells("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"),
               _cells("Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam")),
    # --- scripted time ranges (function at 0x1ECC0C8) ---
    # two "cmp #0xc ; bls ; subs #0xc" conversions -> unconditional skip
    (0x1ECC16A, b"\x00\xd9", b"\x00\xe0"),
    (0x1ECC182, b"\x00\xd9", b"\x00\xe0"),
    # " AM" / " PM" suffixes emptied (only this routine points at them)
    (0x1F0687D, *_slot(encode(" AM") + b"\xff", b"")),
    (0x1F06881, *_slot(encode(" PM") + b"\xff", b"")),
    # --- month abbreviation cells (0x1F81E9E table, iso-length) ---
    (0x1F81E9E, *_slot(encode("Jan. ") + b"\xff", encode("Janv."))),
    (0x1F81EA4, *_slot(encode("Feb. ") + b"\xff", encode("Févr."))),
    (0x1F81EAA, *_slot(encode("Mar. ") + b"\xff", encode("Mars "))),
    (0x1F81EB0, *_slot(encode("Apr. ") + b"\xff", encode("Avr. "))),
    (0x1F81EB6, *_slot(encode("May ") + b"\xff", encode("Mai "))),
    (0x1F81EC1, *_slot(encode("July ") + b"\xff", encode("Juil."))),
    (0x1F81EC7, *_slot(encode("Aug. ") + b"\xff", encode("Août "))),
    (0x1F81ECD, *_slot(encode("Sep. ") + b"\xff", encode("Sept."))),
    (0x1F81EDF, *_slot(encode("Dec. ") + b"\xff", encode("Déc. "))),
    # --- bag menu "Use" → "Utiliser" ---
    # "Use" (3 chars, 4 bytes with 0xFF) lives at 0x4161A0; "Utiliser"
    # (8 chars, 9 bytes) cannot fit in place.  The Spanish translator
    # repointed to 0x284EAB (free space in that build).  The same block
    # is free space (0xFF) in the FR ROM, so we write there and redirect
    # all six pointer entries from 0x084161A0 to 0x08284EAB.
    (0x284EAB, b"\xff" * 9, encode("Utiliser") + b"\xff"),
    (0x452EB8, b"\xa0\x61\x41\x08", b"\xab\x4e\x28\x08"),
    (0x452EE0, b"\xa0\x61\x41\x08", b"\xab\x4e\x28\x08"),
    (0x463150, b"\xa0\x61\x41\x08", b"\xab\x4e\x28\x08"),
    (0x46437C, b"\xa0\x61\x41\x08", b"\xab\x4e\x28\x08"),
    (0xA6BA64, b"\xa0\x61\x41\x08", b"\xab\x4e\x28\x08"),
    (0xA6BA8C, b"\xa0\x61\x41\x08", b"\xab\x4e\x28\x08"),
    # --- dialogue speaker "Mom" → "Maman" ---
    # "Mom" (3 chars, 4 bytes with 0xFF) lives at 0x1F0BA1F (GBA
    # 0x09F0BA1F); "Maman" (5 chars, 6 bytes) cannot fit in place.
    # Free space immediately follows the Utiliser block at 0x284EBC;
    # redirect all five pointer entries from 0x09F0BA1F to 0x08284EBC.
    (0x284EBC, b"\xff" * 6, encode("Maman") + b"\xff"),
    (0x1E6E411, b"\x1f\xba\xf0\x09", b"\xbc\x4e\x28\x08"),
    (0x1E6E432, b"\x1f\xba\xf0\x09", b"\xbc\x4e\x28\x08"),
    (0x1E6E44B, b"\x1f\xba\xf0\x09", b"\xbc\x4e\x28\x08"),
    (0x1E6E47A, b"\x1f\xba\xf0\x09", b"\xbc\x4e\x28\x08"),
    (0x1E6E4B1, b"\x1f\xba\xf0\x09", b"\xbc\x4e\x28\x08"),
]


def apply_patches(data: bytearray, patches=PATCHES) -> int:
    applied = 0
    for offset, old, new in patches:
        if len(old) != len(new):
            raise ValueError(f"0x{offset:X}: length mismatch")
        current = bytes(data[offset : offset + len(old)])
        if current == new:
            continue  # already patched
        if current != old:
            raise ValueError(
                f"0x{offset:X}: unexpected bytes {current.hex(' ')} "
                f"(wanted {old.hex(' ')})"
            )
        data[offset : offset + len(new)] = new
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
    print(f"Time-format patches applied: {applied} (of {len(PATCHES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
