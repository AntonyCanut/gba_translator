#!/usr/bin/env python3
"""Localise les onglets Missions DE sans laisser de catégorie anglaise.

Le moteur concatène une catégorie et un suffixe partagé. La recette DE vide ce
suffixe puis remplace la seule catégorie encore anglaise, ``All``, par
``Alle``. Comme la cellule de quatre octets de ``All`` est trop courte, le
patch réutilise la cellule source ``Completed`` devenue morte après la
relocalisation de son libellé allemand, et repointe uniquement l'onglet All.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import TextDecoder, TextEncoder

ROM_BASE = 0x08000000
SUFFIX_PTR_OFFSET = 0x1EBE988
ALL_TAB_PTR_OFFSET = 0x1EBE978
ACTIVE_TAB_PTR_OFFSET = 0x1FB40B8
INACTIVE_TAB_PTR_OFFSET = 0x1FB40B4
COMPLETED_TAB_PTR_OFFSET = 0x1FB40C0
ALL_INLINE_OFFSET = 0x1F5609F
ALL_RELOCATION_OFFSET = 0x1F560A3
ALLOWED_SUFFIXES = {" Missions", "Missionen", " Missionen"}
ALLOWED_COMPLETED_TABS = {"Abgeschlossen", "Erledigt"}

ENGLISH_ALL_CELL = TextEncoder.encode("All", "pokemon")
ENGLISH_COMPLETED_CELL = TextEncoder.encode("Completed", "pokemon")
_GERMAN_ALL = TextEncoder.encode("Alle", "pokemon")
GERMAN_ALL_CELL = _GERMAN_ALL + b"\xff" * (
    len(ENGLISH_COMPLETED_CELL) - len(_GERMAN_ALL)
)


def _read_text(rom: bytes, offset: int) -> tuple[str, int]:
    end = rom.find(b"\xff", offset, offset + 32)
    if end < 0:
        raise ValueError("Suffix Missions sans terminateur")
    raw = rom[offset : end + 1]
    return TextDecoder.decode_pokemon(raw, preserve_unknown=True), end


def _pointer_target(rom: bytes, pointer_site: int) -> int:
    pointer = struct.unpack_from("<I", rom, pointer_site)[0]
    target = pointer - ROM_BASE
    if not (0 <= target < len(rom)):
        raise ValueError(f"pointeur Missions hors ROM à 0x{pointer_site:X}: 0x{pointer:08X}")
    return target


def apply(rom: bytearray) -> int:
    """Localise suffixe et onglet All atomiquement, avec préimages strictes."""
    candidate = bytearray(rom)
    changed = 0

    suffix_target = _pointer_target(candidate, SUFFIX_PTR_OFFSET)
    if candidate[suffix_target] != 0xFF:
        suffix, end = _read_text(candidate, suffix_target)
        if suffix not in ALLOWED_SUFFIXES:
            raise ValueError(f"Suffix Missions inattendu: {suffix!r}")
        candidate[suffix_target : end + 1] = b"\xff" * (end + 1 - suffix_target)
        changed += 1

    all_target = _pointer_target(candidate, ALL_TAB_PTR_OFFSET)
    current_slot = bytes(
        candidate[
            ALL_RELOCATION_OFFSET :
            ALL_RELOCATION_OFFSET + len(ENGLISH_COMPLETED_CELL)
        ]
    )
    if all_target == ALL_RELOCATION_OFFSET:
        if current_slot != GERMAN_ALL_CELL:
            raise ValueError("onglet Alle repointé vers une cellule inattendue")
    else:
        if all_target != ALL_INLINE_OFFSET:
            raise ValueError(f"pointeur All inattendu: 0x{all_target:X}")
        current_all = bytes(
            candidate[ALL_INLINE_OFFSET : ALL_INLINE_OFFSET + len(ENGLISH_ALL_CELL)]
        )
        if current_all != ENGLISH_ALL_CELL:
            raise ValueError(f"cellule All inattendue: {current_all.hex()}")

        completed_target = _pointer_target(candidate, COMPLETED_TAB_PTR_OFFSET)
        if completed_target == ALL_RELOCATION_OFFSET:
            raise ValueError("la cellule Completed est encore utilisée par son onglet")
        completed_text, _end = _read_text(candidate, completed_target)
        if completed_text not in ALLOWED_COMPLETED_TABS:
            raise ValueError(f"onglet Completed inattendu: {completed_text!r}")
        if current_slot != ENGLISH_COMPLETED_CELL:
            raise ValueError(f"cellule source Completed inattendue: {current_slot.hex()}")

        candidate[
            ALL_RELOCATION_OFFSET :
            ALL_RELOCATION_OFFSET + len(GERMAN_ALL_CELL)
        ] = GERMAN_ALL_CELL
        struct.pack_into(
            "<I", candidate, ALL_TAB_PTR_OFFSET, ROM_BASE + ALL_RELOCATION_OFFSET
        )
        changed += 1

    if changed:
        rom[:] = candidate
    return changed


def main(argv: list[str] | None = None) -> int:
    """Applique le patch à une ROM DE construite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    original = args.rom.read_bytes()
    rom = bytearray(original)
    changed = apply(rom)
    if changed:
        Path(f"{args.rom}.bak").write_bytes(original)
        args.rom.write_bytes(rom)
    print(f"patch_mission_tab_labels_de: {changed} modification(s) d'onglet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
