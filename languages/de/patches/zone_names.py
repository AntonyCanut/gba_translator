#!/usr/bin/env python3
"""Restaure les noms de zones EN originaux dans la ROM allemande."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import TextDecoder

ROOT = Path(__file__).resolve().parents[3]
ROM_BASE = 0x08000000
ENGLISH_NAMES = {
    0x071FC80: "Blizzard City",
    0x0B51EAC: "Antisis Port",
    0x078D811: "Crater Town",
    0x078D851: "Blizzard City",
    0x078D7C8: "Cinder Volcano West",
}
POINTER_SITES = {
    0x071FC80: (0x3F1CBC, 0x721150),
    0x0B51EAC: (0x3F1E34,),
    0x078D811: (0x78D809,),
    0x078D851: (0x78D849,),
    0x078D7C8: (0x78D7C0,),
}
ALLOWED_DE_PREIMAGES = {
    0x0B51EAC: {"Hafen von Antésia"},
    0x078D7C8: {"Aschevulkan West"},
}


def _entry(rom: bytes, offset: int, cap: int = 64) -> tuple[bytes, str]:
    end = rom.find(b"\xff", offset, offset + cap)
    if end < 0:
        raise ValueError(f"zone sans terminateur à 0x{offset:X}")
    raw = rom[offset : end + 1]
    return raw, TextDecoder.decode_pokemon(raw, preserve_unknown=True)


def apply(rom: bytearray, source_rom: bytes) -> int:
    """Restaure atomiquement cellules et pointeurs après validation stricte."""
    if len(rom) != len(source_rom):
        raise ValueError("les ROM source et cible doivent avoir la même taille")
    candidate = bytearray(rom)
    changed = 0
    for offset, english in ENGLISH_NAMES.items():
        source_entry, source_text = _entry(source_rom, offset)
        if source_text != english:
            raise ValueError(
                f"source EN inattendue à 0x{offset:X}: {source_text!r}"
            )
        for site in POINTER_SITES[offset]:
            source_pointer = struct.unpack_from("<I", source_rom, site)[0]
            if source_pointer != ROM_BASE + offset:
                raise ValueError(f"site source de zone inattendu à 0x{site:X}")
            pointer = struct.unpack_from("<I", candidate, site)[0]
            if pointer != ROM_BASE + offset:
                target = pointer - ROM_BASE
                if not (0 <= target < len(candidate)):
                    raise ValueError(f"pointeur de zone hors ROM à 0x{site:X}")
                _raw, current_text = _entry(candidate, target)
                if current_text not in ALLOWED_DE_PREIMAGES.get(offset, set()):
                    raise ValueError(
                        f"pointeur de zone 0x{site:X} cible {current_text!r}"
                    )
                struct.pack_into("<I", candidate, site, ROM_BASE + offset)
                changed += 1
        current_raw, current_text = _entry(candidate, offset)
        if current_raw != source_entry:
            if current_text not in ALLOWED_DE_PREIMAGES.get(offset, set()):
                raise ValueError(
                    f"cellule de zone 0x{offset:X} inattendue: {current_text!r}"
                )
            candidate[offset : offset + len(source_entry)] = source_entry
            changed += 1
    if changed:
        rom[:] = candidate
    return changed


def main(argv: list[str] | None = None) -> int:
    """Applique le patch à une ROM DE construite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument(
        "--source", type=Path, default=ROOT / "input/roms/englishrom.gba"
    )
    args = parser.parse_args(argv)
    original = args.rom.read_bytes()
    rom = bytearray(original)
    changed = apply(rom, args.source.read_bytes())
    if changed:
        Path(f"{args.rom}.bak").write_bytes(original)
        args.rom.write_bytes(rom)
    print(f"patch_zone_names_de: {changed} cellule(s)/pointeur(s) restauré(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
