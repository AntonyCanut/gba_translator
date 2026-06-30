#!/usr/bin/env python3
"""Verify the Black Ferrothorn -> Noirépine gang translation in the BUILT FR ROM.

Unlike the Black Emboar gang (translate_black_emboar_fr.py), these strings are
no-pointer in-place entries (read sequentially by the engine, not relocatable),
so we decode directly at the live offset rather than following a pointer table.

For each target offset we assert:
  - 'Noirépine' is present (translated)
  - no residual 'Black' / 'Ferrothorn' (franglais leftover)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.core.text_codec import TextDecoder

FR = (ROOT / 'output/roms/GenedRom-fr.gba').read_bytes()

TARGETS = [
    0x7F912C, 0x7F9A9A, 0x7F9C81, 0x7FB156, 0x7FB369, 0x7FB9D2, 0x7FBB84,
    0x7FCB63, 0x7FCD63, 0x7FCE4D, 0x7FDB0D, 0x7FDB88,
    0x1EDCDF8, 0x1EDCE5A, 0x1EDCE88, 0x1EDCEB9, 0x1EDD0BD, 0x1EDD100,
    0x1EDD126, 0x1EDD1B1, 0x1EDD1EF, 0x1EDD2A8, 0x1EDDCB0,
    0x1F71D6A,
    0x1F9E5F4, 0x1F9E745, 0x1F9E852, 0x1F9E8EB, 0x1F9EA0C, 0x1F9EA4F,
    0x1F9F08F, 0x1F9F0F2, 0x1F9F3F5, 0x1F9F5A6, 0x1F9F78E, 0x1F9F870,
    0x1F9F92B,
    0x1FA04FC, 0x1FA0625, 0x1FA0D55, 0x1FA0DB8, 0x1FA115F, 0x1FA13F5,
    0x1FA14E0, 0x1FA1B9A,
    0x1FA1EE4, 0x1FA1EF5, 0x1FA1F37, 0x1FA1FA2, 0x1FA1FFE, 0x1FA205D,
    0x1FA20B1, 0x1FA2257, 0x1FA2E41,
]


def decode(off: int, maxlen: int = 600) -> str:
    chunk = FR[off:off + maxlen]
    return TextDecoder.decode_pokemon(chunk, preserve_unknown=True)


def main() -> int:
    fails = []
    for off in TARGETS:
        text = decode(off)
        problems = []
        if 'Noirépine' not in text:
            problems.append('no Noirépine')
        if 'Ferrothorn' in text or 'Black' in text:
            problems.append('residual Black/Ferrothorn')
        status = 'OK' if not problems else 'FAIL:' + ','.join(problems)
        print(f"[{status}] 0x{off:X}: {text[:90]!r}")
        if problems:
            fails.append(f"0x{off:X}: {problems}")

    print(f"\nChecked {len(TARGETS)} live strings.")
    if fails:
        print(f"FAILURES ({len(fails)}):")
        for f in fails:
            print("  ", f)
        return 1
    print("ALL GREEN — every live Black Ferrothorn string is now Noirépine.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
