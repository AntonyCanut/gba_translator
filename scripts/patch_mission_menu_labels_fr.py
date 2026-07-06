#!/usr/bin/env python3
"""
Post-build patch: Mission Menu Labels (French)

Applies French translations to mission menu labels that weren't translated
by the standard pipeline:
  - "All" (0x1F5609F) → "Tous"

These are pointer-based texts with custom handling. The standard injector
skips the "All" label due to padding constraints, so this patch applies it
as a fixed in-place replacement in the built ROM.

Usage:
  python3 scripts/patch_mission_menu_labels_fr.py <rom>

Output:
  Modified ROM with mission menu labels in French
"""

import sys
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.text.charmap_data import CHAR_TO_BYTE


def patch_mission_labels(rom_path: str) -> None:
    """Apply French mission menu label patches to the ROM."""

    # Mission menu label translations
    patches = {
        0x1F5609F: "Tous",  # "All" → "Tous"
    }

    with open(rom_path, 'r+b') as f:
        for offset, text in patches.items():
            # Encode text to CFRU bytes
            text_bytes = bytearray()
            for char in text:
                if char not in CHAR_TO_BYTE:
                    raise ValueError(f"Character '{char}' not in CFRU charmap")
                text_bytes.append(CHAR_TO_BYTE[char])

            text_bytes.append(0xFF)  # Terminator

            # Write to ROM
            f.seek(offset)
            f.write(bytes(text_bytes))

            print(f"✓ Patched 0x{offset:X}: {text}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/patch_mission_menu_labels_fr.py <rom>")
        sys.exit(1)

    rom_path = sys.argv[1]

    if not Path(rom_path).exists():
        print(f"Error: ROM not found: {rom_path}")
        sys.exit(1)

    patch_mission_labels(rom_path)
    print(f"✓ Mission menu label patches applied to {rom_path}")


if __name__ == "__main__":
    main()
