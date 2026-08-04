#!/usr/bin/env python3
"""Make every PC/Box « Move » menu label read « Dépl. » (GitHub issue #29).

Context
-------
Issue #29 asked to abbreviate the French « Déplacer » (which overflowed the row
after the D-pad icon) to « Dépl. » across the compact PC/Box menus. Most cells
are handled through ``combined_fr.txt`` (e.g. 0x4171F1 « Dépl. où ? », the
footer 0x418E77). A handful of labels, however, are
drawn from **hard 4-byte cells** whose English source is exactly « Move » (4
bytes + terminator): 0x418484, 0x418EB5 (« ◄►Move ») and 0xA4E1F1. Into a 5-byte
slot « Dépl. » (5 content bytes + terminator = 6) does not fit, so the inject
pass wrote it in place with no terminator — clobbering the next string and
rendering the corrupt « Dépl.Dépl. où ? » the reporter photographed. Writing
« Dépl » (no period) fits but reads like a truncated word.

These cells are referenced by ordinary 32-bit pointers, so the clean fix is to
relocate: write properly terminated « Dépl. » strings into free ROM space and
repoint every pointer at them. That delivers the period the reporter asked for,
on every menu, with no overflow.

Same PC menu family, one bonus fix: the stored-mail submenu option « Move To
Bag » at 0x4177DD is a *walked* string (no pointer references it — the menu
reads it by walking terminators from « Lire »). Depending on the translation
input used by the generic build, this cell can still contain English or the
older abbreviation « Dépl au sac ». Its slot is exactly 11 bytes, so the
dedicated patch normalizes either preimage to « Vers le sac » in place.

Relocation target
-----------------
0x15FBC90 is a large baseline-free 0xFF block (present in the source ROM and
never touched by the injector or any other post-build patch), so a fixed slot
here is deterministic and collision-free. Same technique as
``party_cancel_button.py`` (which parks « Sortir » in tail padding).

The main PC options at 0x41858D and 0x41859A are ordinary relocatable strings.
Issue #167 restores their full labels through ``combined_fr.txt``; this patch
must not override them with the older abbreviations.

Self-contained, idempotent and self-healing; runs in the ``build-fr`` post-build
chain.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import CHAR_TO_BYTE

ROM_BASE = 0x08000000
TERM = 0xFF
DPAD_ICON = b"\xf8\x0c"  # button-icon control code that prefixes « ◄►Move »

# Deterministic home for the relocated strings: a baseline-free 0xFF block that
# neither the injector nor any other patch writes to.
FREESPACE_BASE = 0x15FBC90


def _enc(text: str) -> bytes:
    return bytes(CHAR_TO_BYTE[c] for c in text)


# Relocation entries: each relocated string + the pointer sites that must target
# it. ``orig`` is the original cell offset (its pointers currently hold
# ROM_BASE|orig); ``prefix`` is raw control-code bytes kept ahead of the text.
#
#   0x418484 « Move »        → « Dépl. »          (2 pointers: box option list)
#   0xA4E1F1 « Move »        → « Dépl. »          (1 pointer: secondary move menu)
#   0x418EB5 « ◄►Move »      → « ◄►Dépl. »        (4 pointers: HUD move hint)
_RELOCATIONS = [
    {
        "label": "Move (box option / secondary menu) -> Dépl.",
        "prefix": b"",
        "text": "Dépl.",
        "pointers": [0x3D3548, 0x9A41C4, 0xA6CAAC],
        "orig": {0x3D3548: 0x418484, 0x9A41C4: 0x418484, 0xA6CAAC: 0xA4E1F1},
    },
    {
        "label": "◄►Move (HUD hint) -> ◄►Dépl.",
        "prefix": DPAD_ICON,
        "text": "Dépl.",
        "pointers": [0xC05D8, 0xC12E0, 0xC283C, 0xC4FE8],
        "orig": {0xC05D8: 0x418EB5, 0xC12E0: 0x418EB5, 0xC283C: 0x418EB5, 0xC4FE8: 0x418EB5},
    },
]

# In-place, pointer-less walked string in the stored-mail submenu.
MAIL_MOVE_TO_BAG_OFFSET = 0x4177DD
MAIL_MOVE_TO_BAG_EN = _enc("Move To Bag")          # 11 bytes (CFRU-encoded)
MAIL_MOVE_TO_BAG_LEGACY_FR = _enc("Dépl au sac")   # 11-byte generic abbreviation
MAIL_MOVE_TO_BAG_FR = _enc("Vers le sac")          # 11 bytes, exact fit
MAIL_MOVE_TO_BAG_PREIMAGES = (MAIL_MOVE_TO_BAG_EN, MAIL_MOVE_TO_BAG_LEGACY_FR)


def apply(rom: bytearray) -> int:
    patched = 0

    # --- relocation entries -------------------------------------------------
    cursor = FREESPACE_BASE
    for entry in _RELOCATIONS:
        blob = entry["prefix"] + _enc(entry["text"]) + bytes([TERM])
        slot = cursor
        cursor += len(blob)
        new_addr = ROM_BASE | slot

        # Reserve the slot only when at least one pointer still needs it.
        need_write = False
        for loc in entry["pointers"]:
            cur = struct.unpack_from("<I", rom, loc)[0]
            if cur == new_addr:
                continue  # already repointed (idempotent)
            expected = ROM_BASE | entry["orig"][loc]
            if cur != expected:
                print(
                    f"  WARN {entry['label']}: pointer 0x{loc:07X} -> 0x{cur:08X} "
                    f"(expected 0x{expected:08X}) — skip this site",
                    file=sys.stderr,
                )
                continue
            need_write = True

        if not need_write:
            continue

        # The free slot must be untouched 0xFF (or already hold our blob).
        current_slot = bytes(rom[slot:slot + len(blob)])
        if current_slot != blob and any(b != TERM for b in current_slot):
            print(
                f"  ERROR {entry['label']}: free slot 0x{slot:07X} is not free "
                f"({current_slot.hex()}) — skip",
                file=sys.stderr,
            )
            continue

        rom[slot:slot + len(blob)] = blob
        for loc in entry["pointers"]:
            cur = struct.unpack_from("<I", rom, loc)[0]
            expected = ROM_BASE | entry["orig"][loc]
            if cur == expected:
                struct.pack_into("<I", rom, loc, new_addr)
                patched += 1
        print(f"  0x{slot:07X}  {entry['label']}")

    # --- in-place walked mail string ---------------------------------------
    off = MAIL_MOVE_TO_BAG_OFFSET
    cur = bytes(rom[off:off + len(MAIL_MOVE_TO_BAG_EN)])
    if cur == MAIL_MOVE_TO_BAG_FR:
        pass  # already applied
    elif cur not in MAIL_MOVE_TO_BAG_PREIMAGES:
        print(
            f"  WARN mail « Move To Bag » 0x{off:07X}: expected a supported preimage, "
            f"found {cur.hex()} — skip",
            file=sys.stderr,
        )
    else:
        rom[off:off + len(MAIL_MOVE_TO_BAG_FR)] = MAIL_MOVE_TO_BAG_FR
        print(f"  0x{off:07X}  mail « Move To Bag » → « Vers le sac »")
        patched += 1

    return patched


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=Path, default=Path("output/roms/GenedRom-fr.gba"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    rom = bytearray(args.rom.read_bytes())
    if rom[0xB2] != 0x96:
        raise SystemExit(f"Not a valid GBA ROM: {args.rom}")
    n = apply(rom)
    if n and not args.dry_run:
        args.rom.write_bytes(rom)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_pc_move_labels_fr: {n} pointer(s)/string(s) patched{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
