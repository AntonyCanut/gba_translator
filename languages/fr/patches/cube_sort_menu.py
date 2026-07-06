#!/usr/bin/env python3
"""Patch the Cube's item-pocket "Sort" submenu (issue #25).

These five strings render the "Sort" popup inside the Bag/Cube (choose a
pocket, then "Sort this pocket's items how?" -> Type/Name/Amount -> "Sort
items by X?" / "Items sorted by X!"). combined_fr.txt already carries a
French translation for each offset, but none of it ever reaches the built
ROM: a live-pointer search of the built ROM finds no pointer to any of
these five addresses (unlike the neighboring "Type"/"Nom"/"Plus"/"Moins"
cells in the same table, which are pointer-reachable and already render in
French). With no pointer to update, the reinjection pass cannot relocate a
longer French string here, so it silently skips these five and the
original English bytes ship untouched — same class as
`patch_options_footer_fr.py` / `patch_status_abbrevs_fr.py`. Each slot is
packed byte-tight against the next string, so replacement text must fit
within (or under) the original English byte length; direct in-place patch,
byte-exact, applied after the build.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.text.charmap_data import CHAR_TO_BYTE

NEWLINE = b"\xfe"
STR_VAR_1 = b"\xfd\x02"  # buffer holding the sort-criterion name (Type/Nom/Quantité)


def _encode(text: str) -> bytes:
    return bytes(CHAR_TO_BYTE[c] for c in text)


# offset -> (expected EN original bytes incl. terminator, FR content bytes
# excl. terminator, slot size in bytes incl. terminator)
_ENTRIES: dict[int, tuple[bytes, bytes, int]] = {
    0xA4E047: (
        bytes.fromhex("cde3e6e800e8dcdde700e4e3d7dfd9e8b4e7fedde8d9e1e700dce3ebacff"),
        _encode("Comment trier") + NEWLINE + _encode("cette poche ?"),
        30,
    ),
    0xA4E07A: (
        bytes.fromhex("bbe1e3e9e2e8ff"),
        _encode("Nombre"),
        7,
    ),
    0xA4E096: (
        bytes.fromhex("d5e1e3e9e2e8ff"),
        _encode("nombre"),
        7,
    ),
    0xA4E09D: (
        bytes.fromhex("cde3e6e800dde8d9e1e700d6edfefd02acff"),
        _encode("Trier par") + NEWLINE + STR_VAR_1 + _encode(" ?"),
        18,
    ),
    0xA4E0AF: (
        bytes.fromhex("c3e8d9e1e700e7e3e6e8d9d800d6edfefd02abff"),
        _encode("Triés par") + NEWLINE + STR_VAR_1 + _encode(" !"),
        20,
    ),
}


def apply_patch(rom_path: Path, dry_run: bool = False) -> int:
    rom = bytearray(rom_path.read_bytes())
    patched = 0

    for offset, (en_original, fr_content, slot) in _ENTRIES.items():
        fr_bytes = fr_content + b"\xff"
        if len(fr_bytes) > slot:
            print(
                f"  ERROR 0x{offset:07X}: FR bytes ({len(fr_bytes)}) exceed slot ({slot}) — skip",
                file=sys.stderr,
            )
            continue

        current = bytes(rom[offset : offset + slot])
        if current[: len(fr_bytes)] == fr_bytes:
            continue  # already applied

        if bytes(rom[offset : offset + len(en_original)]) != en_original:
            print(
                f"  WARN 0x{offset:07X}: expected EN original, "
                f"found {current[:len(en_original)].hex()} — skip",
                file=sys.stderr,
            )
            continue

        if not dry_run:
            rom[offset : offset + len(fr_bytes)] = fr_bytes
            rom[offset + len(fr_bytes) : offset + slot] = bytes(slot - len(fr_bytes))
            rom_path.write_bytes(rom)

        print(f"  0x{offset:07X}  Cube sort-menu string -> FR")
        patched += 1

    return patched


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    n = apply_patch(args.rom, dry_run=args.dry_run)
    suffix = " (dry-run)" if args.dry_run else ""
    print(f"patch_cube_sort_menu_fr: {n} patch(es) applied{suffix}")


if __name__ == "__main__":
    main()
