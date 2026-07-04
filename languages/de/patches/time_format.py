#!/usr/bin/env python3
"""Switch the in-game date/time displays to German conventions.

Port of ``patch_time_format_fr.py`` (see that file for the full background:
none of these displays are reachable by the text pipeline, so this is a
post-build patch against the built ROM). The underlying ASM logic (12h->24h
conversion branches, leading-zero rendering) is engine code shared by every
language build and is copied here unchanged; only the assembled strings
differ for German conventions:

- save screen: forced 24h, template rewritten to "DD.MM.YYYY HH:MM" (dot
  separators, day-month-year order, AM/PM token dropped), "Never" -> "Niemals";
- start-menu clock: forced 24h, leading-zero hour, template rewritten to
  "Www. HH:MM" (the weekday-abbreviation + time layout is locale-neutral, so
  only the seven weekday cells change: So./Mo./Di./Mi./Do./Fr./Sa. via the
  3-letter forms Son/Mon/Die/Mit/Don/Fre/Sam);
- scripted time ranges: both 12-hour conversions disabled, the " AM" / " PM"
  suffix strings emptied (24h has no suffix);
- month-abbreviation cells: written through the *live* month-pointer table
  (0x1FE6BFC), not the original fixed-table offsets. The WIP German pipeline
  auto-fills any month cell without a combined_de.txt entry from the Spanish
  column whenever it differs from English, relocating it to free space if
  needed — so several cells are neither at their original address nor still
  English (e.g. Jan./Apr./Aug. currently hold Spanish "Ene."/"Abr."/"Ago.",
  even though the *English* spelling for those three happens to already be
  correct German). Patching the original fixed offset would silently miss
  the cell the game actually reads — the exact live-pointer trap documented
  in project memory. Feb./Jun./Nov. are left alone because whatever is
  already there (English or the Spanish fallback) coincides with the correct
  German abbreviation.

Out of scope: the FR script also relocates two unrelated labels ("Use" ->
"Utiliser", "Mom" -> "Maman") into FR-build-specific free space. Those are
ordinary extractable strings (not date/time code), not tracked as part of
this DE gap, and the free-space addresses are not guaranteed clear in the
generic DE build — they belong in the normal combined_de.txt pipeline
instead, so this port does not touch them.

Every patch verifies the bytes it expects (English original) and is
idempotent (already-patched cells are skipped).

Usage:
    python3 languages/de/patches/time_format.py --rom output/roms/GenedRom-de.gba
"""

from __future__ import annotations

import argparse
import struct
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
DOT, COLON, SPACE = b"\xad", b"\xf0", b"\x00"

# Save-screen region 0x1F11DAC-0x1F11DCF holds "{COLOR}{SHADOW}Never" then
# the date template "{COLOR}{SHADOW}Y/M/D h:mm ampm". "Niemals" is two bytes
# longer than "Never", but the German template (no AM/PM token) is three
# bytes shorter, so the region is re-laid-out as a whole: Niemals ends at
# 0x1F11DB9, the D.M.Y HH:MM template starts at 0x1F11DBA, and the
# template's single pointer (in the 0x1EB6260 literal pool slot) follows.
SAVE_TEMPLATE_OLD = (
    FC(0x01, 0x02) + FC(0x03, 0x03)
    + FD(0x02) + b"\xba" + FD(0x03) + b"\xba" + FD(0x04)
    + SPACE + FD(0x07) + COLON + FD(0x08) + SPACE + FD(0x0A) + b"\xff"
)
SAVE_TEMPLATE_NEW = (
    FC(0x01, 0x02) + FC(0x03, 0x03)
    + FD(0x04) + DOT + FD(0x03) + DOT + FD(0x02)
    + SPACE + FD(0x07) + COLON + FD(0x08) + b"\xff"
)

# Start-menu clock template: "Www. h:mm ampm" -> "Www. HH:MM" — locale
# neutral (weekday + dot + time), only the weekday cells below change.
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
        FC(0x01, 0x02) + FC(0x03, 0x03) + encode("Niemals") + b"\xff"
        + SAVE_TEMPLATE_NEW,
    )),
    # template pointer 0x09F11DB8 -> 0x09F11DBA in the literal pool
    (0x1EB6260, b"\xb8\x1d\xf1\x09", b"\xba\x1d\xf1\x09"),
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
               _cells("Son", "Mon", "Die", "Mit", "Don", "Fre", "Sam")),
    # --- scripted time ranges (function at 0x1ECC0C8) ---
    # two "cmp #0xc ; bls ; subs #0xc" conversions -> unconditional skip
    (0x1ECC16A, b"\x00\xd9", b"\x00\xe0"),
    (0x1ECC182, b"\x00\xd9", b"\x00\xe0"),
    # " AM" / " PM" suffixes emptied (only this routine points at them)
    (0x1F0687D, *_slot(encode(" AM") + b"\xff", b"")),
    (0x1F06881, *_slot(encode(" PM") + b"\xff", b"")),
]

# --- month abbreviation cells, addressed via the live pointer table -------
# 12 pointers (month 1..12), same table patch_trainer_card_date_de.py reads.
#
# NOTE: this must go through the *live* pointer, not the original fixed-table
# offset. The WIP German pipeline auto-fills any cell it has no combined_de.txt
# entry for with the Spanish column whenever ES differs from EN, and relocates
# it to free space if needed — so months 1/4/6/7/8 are not sitting at their
# original address, and (worse) months 1/4/8 currently hold Spanish text
# ("Ene."/"Abr."/"Ago.") even though their *English* spelling happens to be
# German-identical (Jan./Apr./Aug.). All entries below are therefore patched
# explicitly rather than assumed-correct-if-untouched. Feb./Nov. are omitted
# because whatever the pipeline currently has there (English or Spanish
# fallback) already equals the correct German abbreviation; June's Spanish
# fallback "Jun." also happens to be the correct German one.
MONTH_PTR_TABLE_FILE = 0x1FE6BFC
MONTH_DE = {
    1: "Jan.",
    3: "März ",
    4: "Apr.",
    5: "Mai ",
    # Keep July to the 4-byte abbreviation: the generic DE build can relocate
    # this month to a live slot that is only four content bytes wide.
    7: "Juli",
    8: "Aug.",
    9: "Sept.",
    10: "Okt. ",
    12: "Dez. ",
}


def patch_months(data: bytearray) -> int:
    changed = 0
    for month, text in MONTH_DE.items():
        ptr_off = MONTH_PTR_TABLE_FILE + 4 * (month - 1)
        ptr = struct.unpack("<I", data[ptr_off : ptr_off + 4])[0]
        file_off = ptr - 0x08000000
        i = file_off
        while data[i] != 0xFF:
            i += 1
        cur_len = i - file_off
        new_bytes = encode(text)
        if len(new_bytes) > cur_len:
            raise ValueError(
                f"month {month}: '{text}' ({len(new_bytes)}B) does not fit "
                f"the current slot at 0x{file_off:X} ({cur_len}B)"
            )
        region = new_bytes + b"\xff" * (cur_len + 1 - len(new_bytes))
        current = bytes(data[file_off : file_off + len(region)])
        if current == region:
            continue  # already patched
        data[file_off : file_off + len(region)] = region
        changed += 1
    return changed


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
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-de.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    applied = apply_patches(data)
    applied += patch_months(data)
    if applied:
        args.rom.write_bytes(data)
    print(f"Time-format patches applied: {applied} (of {len(PATCHES) + len(MONTH_DE)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
