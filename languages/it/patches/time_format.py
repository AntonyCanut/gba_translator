#!/usr/bin/env python3
"""Switch the in-game date/time displays to Italian conventions.

Port of ``patch_time_format_fr.py`` (see that file for the full background:
none of these displays are reachable by the text pipeline, so this is a
post-build patch against the built ROM). The underlying ASM logic (12h->24h
conversion branches, leading-zero rendering) is engine code shared by every
language build and is copied here unchanged; only the assembled strings
differ for Italian conventions:

- save screen: forced 24h, "Never" -> "Mai" in place, template rewritten to
  "DD/MM/YYYY HH:MM" (slash separators, day-month-year order — same
  convention as French — AM/PM token dropped);
- start-menu clock: forced 24h, leading-zero hour, template rewritten to
  "Www. HH:MM" (locale-neutral layout, only the seven weekday cells change:
  Dom/Lun/Mar/Mer/Gio/Ven/Sab);
- scripted time ranges: both 12-hour conversions disabled, the " AM" / " PM"
  suffix strings emptied (24h has no suffix);
- month-abbreviation cells: unlike the DE port, these do NOT need a dedicated
  post-build step here. The month cells at their classic fixed-table offsets
  (0x1F81E9E..0x1F81EDF) are plain printable strings the IT extractor's
  ``--scan-all-pointers`` picks up like any other, so
  ``languages/it/combined_it.txt`` already carries all 12 Italian
  abbreviations (Gen./Feb./Mar./Apr./Mag./Giu./Lug./Ago./Set./Ott./Nov./
  Dic.) and the initial ROM build (not this script) writes them.

Out of scope: the FR script also relocates two unrelated labels ("Use" ->
"Utiliser", "Mom" -> "Maman") into FR-build-specific free space. Those are
ordinary extractable strings (not date/time code), not part of this IT gap,
and the free-space addresses are not guaranteed clear in the generic IT
build — they belong in the normal combined_it.txt pipeline instead, so this
port does not touch them (same scoping decision as the DE port).

Save-screen template quirk: the FR/DE scripts patch the "Never" word and the
date template as ONE contiguous byte region (they sit back-to-back at a
fixed offset in those builds) and rewrite the single literal-pool pointer at
0x1EB6260 to account for "Never" shrinking. That assumption does not hold
for the IT generic build: the initial ROM build's own relocation pass
independently moves a byte-identical copy of the date-template blob
elsewhere in ROM and repoints 0x1EB6260 at the copy — a pre-existing
pipeline behaviour unrelated to any text this script or combined_it.txt
authors (reproduced even with no Italian translation touching this area at
all). So this port treats the word and the template as two independent,
non-relocating edits instead:
  - the "Never" word is patched in place at its own fixed offset (it never
    moves — the template's possible relocation doesn't change its address);
  - the template is patched wherever the LIVE 0x1EB6260 pointer currently
    resolves to (its original fixed spot, or the pipeline's relocated copy),
    shrunk in place with 0xFF padding — never moved again, so no pointer
    rewrite is needed either way.

Every patch verifies the bytes it expects (English original) and is
idempotent (already-patched cells are skipped).

Usage:
    python3 languages/it/patches/time_format.py --rom output/roms/GenedRom-it.gba
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
SLASH, COLON, SPACE = b"\xba", b"\xf0", b"\x00"

# "Never" word cell at 0x1F11DAC (fixed — see module docstring for why it is
# patched independently of the date template that used to sit right after it).
NEVER_OFFSET = 0x1F11DAC
NEVER_OLD, NEVER_NEW = _slot(
    FC(0x01, 0x02) + FC(0x03, 0x03) + encode("Never") + b"\xff",
    FC(0x01, 0x02) + FC(0x03, 0x03) + encode("Mai") + b"\xff",
)

# Date template: "{COLOR}{SHADOW}Y/M/D h:mm ampm" -> "{COLOR}{SHADOW}D/M/Y HH:MM".
# Patched wherever the live 0x1EB6260 literal-pool pointer resolves to (see
# module docstring) rather than at a hardcoded offset.
SAVE_TEMPLATE_PTR_SLOT = 0x1EB6260
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

# Start-menu clock template: "Www. h:mm ampm" -> "Www. HH:MM"
CLOCK_TEMPLATE_OLD = (
    FD(0x0C) + b"\xad" + SPACE + FD(0x02) + COLON + FD(0x03)
    + SPACE + FD(0x04) + b"\xff"
)
CLOCK_TEMPLATE_NEW = FD(0x0C) + b"\xad" + SPACE + FD(0x02) + COLON + FD(0x03) + b"\xff"

# (offset, expected bytes, replacement bytes) — same length, byte-exact.
PATCHES = [
    # --- save screen (function at 0x1EB5EEC) ---
    # cmp r3,#0xc ; bls -> b : skip the "hour -= 12" path entirely
    (0x1EB5F12, b"\x04\xd9", b"\x04\xe0"),
    # hour ConvertIntToDecimalStringN mode: movs r2,r5 (0) -> movs r2,#2
    (0x1EB614C, b"\x2a\x00", b"\x02\x22"),
    # "Never" -> "Mai" word cell (see NEVER_OFFSET above)
    (NEVER_OFFSET, NEVER_OLD, NEVER_NEW),
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
               _cells("Dom", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab")),
    # --- scripted time ranges (function at 0x1ECC0C8) ---
    # two "cmp #0xc ; bls ; subs #0xc" conversions -> unconditional skip
    (0x1ECC16A, b"\x00\xd9", b"\x00\xe0"),
    (0x1ECC182, b"\x00\xd9", b"\x00\xe0"),
    # " AM" / " PM" suffixes emptied (only this routine points at them)
    (0x1F0687D, *_slot(encode(" AM") + b"\xff", b"")),
    (0x1F06881, *_slot(encode(" PM") + b"\xff", b"")),
]


def patch_save_template(data: bytearray) -> int:
    """Patch the date template in place, wherever its live pointer resolves to."""
    ptr = struct.unpack_from("<I", data, SAVE_TEMPLATE_PTR_SLOT)[0]
    file_off = ptr - 0x08000000
    old, new = _slot(SAVE_TEMPLATE_OLD, SAVE_TEMPLATE_NEW)
    current = bytes(data[file_off : file_off + len(old)])
    if current == new:
        return 0  # already patched
    if current != old:
        raise ValueError(
            f"save-template @0x{file_off:X} (via pointer 0x{ptr:08X}): "
            f"unexpected bytes {current.hex(' ')} (wanted {old.hex(' ')})"
        )
    data[file_off : file_off + len(new)] = new
    return 1


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
    parser.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-it.gba"))
    args = parser.parse_args()

    data = bytearray(args.rom.read_bytes())
    applied = apply_patches(data)
    applied += patch_save_template(data)
    if applied:
        args.rom.write_bytes(data)
    print(f"Time-format patches applied: {applied} (of {len(PATCHES) + 1})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
