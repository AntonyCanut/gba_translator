#!/usr/bin/env python3
"""
Patch PC-related messages for French translation.

These offsets are not covered by the standard translation pipeline
(neither pointers nor inline extraction caught them). Apply French
translations directly to the ROM.

Messages:
- 0x1A5CF1: "transferred to Someone's PC" → "le PC de ???"
- 0x1A5D6E: "Someone's PC was full" → "PC de ???"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import TextEncoder


PATCHES = [
    # offset: (english_original, french_translation)
    (0x1A5CF1,
     '{FD:03} was transferred to\nSomeone\'s PC.{PAGE}It was placed in \nBox "{FD:02}."',
     '{FD:03} a été transféré vers\nle PC de ???.\pIl a été placé dans\nla Boîte {FD:02}.'),

    (0x1A5D6E,
     'Box "{FD:04}" on\nSomeone\'s PC was full.{PAGE}{FD:03} was transferred to\nBox "{FD:02}."',
     'La Boîte {FD:04} du PC de\n??? était pleine.\p{FD:03} a été transféré dans\nla Boîte {FD:02}.'),
]


def patch_pc_messages(rom_path: Path) -> int:
    """Apply French PC message translations. Return count of patches applied."""
    with open(rom_path, 'r+b') as f:
        rom_data = bytearray(f.read())

        for offset, english_text, french_text in PATCHES:
            # Normalize control codes in the French text
            normalized_fr = (
                french_text
                .replace('{FD:03}', '<0xFD><0x03>')
                .replace('{FD:04}', '<0xFD><0x04>')
                .replace('{FD:02}', '<0xFD><0x02>')
                .replace('{FD:01}', '<0xFD><0x01>')
                .replace('\\n', '\n')
                .replace('\\p', '<0xFB>')
            )

            # Encode to GBA Pokemon format
            encoded = TextEncoder.encode(normalized_fr, 'pokemon')

            # Write to ROM data
            rom_data[offset:offset + len(encoded)] = encoded
            print(f"✓ Patched 0x{offset:X}: {len(encoded)} bytes")

        # Save ROM
        f.seek(0)
        f.write(rom_data)
        f.truncate()

    return len(PATCHES)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Patch PC-related messages for French translation'
    )
    parser.add_argument(
        '--rom',
        type=Path,
        required=True,
        help='Path to the built French ROM'
    )

    args = parser.parse_args()

    if not args.rom.exists():
        print(f"Error: ROM not found: {args.rom}")
        return 1

    applied = patch_pc_messages(args.rom)
    print(f"\n✅ Successfully patched {applied} PC messages")
    return 0


if __name__ == '__main__':
    sys.exit(main())
