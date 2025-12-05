#!/usr/bin/env python3
"""
Scanne un ROM GBA et produit un fichier listant toutes les zones
utilisées/libres (runs de 0xFF) avec start/end/size/type.

Usage :
    python dump_rom_usage.py --rom totranslate.gba --out rom_usage.txt
"""

from __future__ import annotations

import argparse
from pathlib import Path


def dump_usage(rom: Path, out: Path) -> None:
    data = rom.read_bytes()
    n = len(data)
    entries = []
    i = 0
    while i < n:
        free = data[i] == 0xFF
        start = i
        while i < n and (data[i] == 0xFF) == free:
            i += 1
        end = i  # exclu
        size = end - start
        entries.append((start, end, size, "free" if free else "used"))
    lines = [f"{hex(s)} {hex(e)} {size} {typ}" for s, e, size, typ in entries]
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"{out} écrit ({len(entries)} blocs).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump des zones utilisées/libres d'un ROM GBA.")
    parser.add_argument("--rom", type=Path, default=Path("totranslate.gba"), help="ROM à analyser")
    parser.add_argument("--out", type=Path, default=Path("rom_usage.txt"), help="Fichier de sortie")
    args = parser.parse_args()
    dump_usage(args.rom, args.out)


if __name__ == "__main__":
    main()
