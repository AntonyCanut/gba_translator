#!/usr/bin/env python3
"""
Patch PC-related messages for German translation.

Port of ``patch_pc_messages_fr.py``. These offsets are not covered by the
standard translation pipeline (neither pointers nor inline extraction caught
them). Apply German translations directly to the ROM.

Messages:
- 0x1A5CF1: "transferred to Someone's PC" -> "wurde aufs PC von ??? verschoben"
- 0x1A5D6E: "Someone's PC was full" -> "PC von ??? war voll"

Both slots are a fixed number of bytes (no relocation possible here — no
pointer was found to repoint, the code likely jumps to this address
directly): the raw English strings decode to 64 and 67 bytes respectively,
with a single following 0xFF and no slack before real ROM content resumes.
A literal translation of the English/French wording overflows both slots by
several bytes, which would corrupt the following ROM data — so both German
strings below are deliberately shortened (dropping the quote marks around
the box number, same simplification the French version already makes) to
fit within the original English byte count. ``apply`` re-verifies this at
write time and refuses to write anything that doesn't fit.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.core.text_codec import TextEncoder


PATCHES = [
    # offset: (english_original, german_translation, max_encoded_bytes)
    (0x1A5CF1,
     '{FD:03} was transferred to\nSomeone\'s PC.{PAGE}It was placed in \nBox "{FD:02}."',
     '{FD:03} wurde aufs PC von\n??? verschoben.\pEs kam in Box\n{FD:02}.',
     64),

    (0x1A5D6E,
     'Box "{FD:04}" on\nSomeone\'s PC was full.{PAGE}{FD:03} was transferred to\nBox "{FD:02}."',
     'Box {FD:04} auf dem PC\nvon ??? war voll.\p{FD:03} kam in Box\n{FD:02}.',
     67),
]


def patch_pc_messages(rom_path: Path) -> int:
    """Apply German PC message translations. Return count of patches applied."""
    with open(rom_path, 'r+b') as f:
        rom_data = bytearray(f.read())

        for offset, english_text, german_text, max_bytes in PATCHES:
            # Normalize control codes in the German text
            normalized_de = (
                german_text
                .replace('{FD:03}', '<0xFD><0x03>')
                .replace('{FD:04}', '<0xFD><0x04>')
                .replace('{FD:02}', '<0xFD><0x02>')
                .replace('{FD:01}', '<0xFD><0x01>')
                .replace('\\n', '\n')
                .replace('\\p', '<0xFB>')
            )

            # Encode to GBA Pokemon format
            encoded = TextEncoder.encode(normalized_de, 'pokemon')
            if len(encoded) > max_bytes:
                raise ValueError(
                    f"0x{offset:X}: German text encodes to {len(encoded)} bytes, "
                    f"exceeds the {max_bytes}-byte slot — would corrupt the next cell"
                )

            # Write to ROM data
            rom_data[offset:offset + len(encoded)] = encoded
            print(f"✓ Patched 0x{offset:X}: {len(encoded)} bytes (of {max_bytes} available)")

        # Save ROM
        f.seek(0)
        f.write(rom_data)
        f.truncate()

    return len(PATCHES)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Patch PC-related messages for German translation'
    )
    parser.add_argument(
        '--rom',
        type=Path,
        required=True,
        help='Path to the built German ROM'
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
