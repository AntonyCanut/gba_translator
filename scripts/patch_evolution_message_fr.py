#!/usr/bin/env python3
"""
Patch the evolution message at 0x3FE673 with the French translation.

This offset is an "in-place" entry that doesn't go through the normal
pointer-based translation pipeline. It's the same in English and Spanish,
and needs a dedicated post-build patch for French.

Offset: 0x3FE673
English: hat?\n{FD02} is evolving!  (20 bytes)
French:  Quoi ?\n{FD02} évolue !    (18 bytes, fits in space)
"""

import sys
from pathlib import Path


def patch_evolution_message(rom_path):
    """Patch the evolution message in the French ROM."""

    # The French bytes (encoded)
    # CB (Q) E9 (u) E3 (o) DD (i) 00 (space) AC (?) FA (\n) FD 02 (Pokemon name)
    # 00 (space) 1B (é) EA (v) E3 (o) E0 (l) E9 (u) D9 (e) 00 (space) AB (!)
    french_bytes = bytes([
        0xCB, 0xE9, 0xE3, 0xDD, 0x00, 0xAC,  # "Quoi ?"
        0xFA,                                   # newline
        0xFD, 0x02,                             # Pokemon name placeholder
        0x00,                                   # space
        0x1B, 0xEA, 0xE3, 0xE0, 0xE9, 0xD9,  # "évolue"
        0x00, 0xAB                              # " !"
    ])

    offset = 0x3FE673

    # Pad with 0xFF if needed (English version is 20 bytes, French is 18)
    # We'll write 18 bytes and leave 2 bytes as padding
    padding_needed = 20 - len(french_bytes)
    french_bytes = french_bytes + bytes([0xFF] * padding_needed)

    with open(rom_path, 'r+b') as f:
        f.seek(offset)
        f.write(french_bytes)

    print(f"✓ Patched evolution message at 0x{offset:08X}")
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <rom_path>")
        sys.exit(1)

    rom_path = Path(sys.argv[1])
    if not rom_path.exists():
        print(f"Error: ROM not found at {rom_path}")
        sys.exit(1)

    try:
        patch_evolution_message(rom_path)
        print("Evolution message patched successfully!")
    except Exception as e:
        print(f"Error patching ROM: {e}")
        sys.exit(1)
