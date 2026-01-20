#!/usr/bin/env python3
"""
Advanced GBA ROM Text Translation Tool with Relocation Support

This script can:
- Translate texts that are longer than the original
- Automatically relocate texts to free space
- Update all pointers to relocated texts
- Handle both ASCII and Pokemon encoding
"""

import sys
import json
import struct
from pathlib import Path
from collections import defaultdict


class ROMTranslator:
    GBA_ROM_BASE = 0x08000000  # GBA ROM memory base address

    def __init__(self, rom_path, translation_json):
        self.rom_path = Path(rom_path)
        self.translation_json = Path(translation_json)
        self.rom_data = bytearray()
        self.texts_data = None
        self.free_space_offset = None
        self.relocated_texts = []
        self.pointer_updates = {}

    def load_rom(self):
        """Load ROM into memory."""
        with open(self.rom_path, 'rb') as f:
            self.rom_data = bytearray(f.read())
        print(f"Loaded ROM: {self.rom_path.name} ({len(self.rom_data)} bytes)")

    def load_texts(self):
        """Load translation data from JSON."""
        with open(self.translation_json, 'r', encoding='utf-8') as f:
            self.texts_data = json.load(f)
        print(f"Loaded {len(self.texts_data['texts'])} text entries")

    def find_free_space(self, min_size=50000):
        """
        Find a large contiguous block of free space (0xFF bytes).

        Returns:
            offset of free space block
        """
        print(f"\nSearching for free space (min {min_size} bytes)...")

        in_free_block = False
        block_start = 0

        for i in range(len(self.rom_data)):
            if self.rom_data[i] == 0xFF:
                if not in_free_block:
                    in_free_block = True
                    block_start = i
            else:
                if in_free_block:
                    block_size = i - block_start
                    if block_size >= min_size:
                        print(f"Found free space at 0x{block_start:08X} ({block_size} bytes)")
                        return block_start
                    in_free_block = False

        # Check if we ended in a free block
        if in_free_block:
            block_size = len(self.rom_data) - block_start
            if block_size >= min_size:
                print(f"Found free space at 0x{block_start:08X} ({block_size} bytes)")
                return block_start

        raise Exception("No suitable free space found in ROM")

    def find_pointers_to_offset(self, target_offset):
        """
        Find all pointers that reference a specific ROM offset.

        Args:
            target_offset: ROM offset to search for

        Returns:
            List of pointer locations
        """
        target_pointer = self.GBA_ROM_BASE + target_offset
        target_bytes = struct.pack('<I', target_pointer)

        pointers = []
        i = 0
        while i < len(self.rom_data) - 3:
            if self.rom_data[i:i+4] == target_bytes:
                pointers.append(i)
                i += 4
            else:
                i += 1

        return pointers

    def encode_pokemon_string(self, text):
        """Encode string using Pokemon character table."""
        CHAR_TO_POKEMON = {
            ' ': 0x00, 'A': 0xBB, 'B': 0xBC, 'C': 0xBD, 'D': 0xBE, 'E': 0xBF,
            'F': 0xC0, 'G': 0xC1, 'H': 0xC2, 'I': 0xC3, 'J': 0xC4, 'K': 0xC5,
            'L': 0xC6, 'M': 0xC7, 'N': 0xC8, 'O': 0xC9, 'P': 0xCA, 'Q': 0xCB,
            'R': 0xCC, 'S': 0xCD, 'T': 0xCE, 'U': 0xCF, 'V': 0xD0, 'W': 0xD1,
            'X': 0xD2, 'Y': 0xD3, 'Z': 0xD4, 'a': 0xD5, 'b': 0xD6, 'c': 0xD7,
            'd': 0xD8, 'e': 0xD9, 'f': 0xDA, 'g': 0xDB, 'h': 0xDC, 'i': 0xDD,
            'j': 0xDE, 'k': 0xDF, 'l': 0xE0, 'm': 0xE1, 'n': 0xE2, 'o': 0xE3,
            'p': 0xE4, 'q': 0xE5, 'r': 0xE6, 's': 0xE7, 't': 0xE8, 'u': 0xE9,
            'v': 0xEA, 'w': 0xEB, 'x': 0xEC, 'y': 0xED, 'z': 0xEE,
            '0': 0xA1, '1': 0xA2, '2': 0xA3, '3': 0xA4, '4': 0xA5,
            '5': 0xA6, '6': 0xA7, '7': 0xA8, '8': 0xA9, '9': 0xAA,
            '!': 0xAB, '?': 0xAC, '.': 0xAD, '-': 0xAE, ',': 0xB8,
            '\n': 0xFE, '\'': 0xB4, ':': 0xF0, '(': 0xA8, ')': 0xA9,
            ';': 0xB9, '[': 0xF7, ']': 0xF8, '&': 0xF1, '/': 0xF2
        }

        encoded = bytearray()
        for char in text:
            if char in CHAR_TO_POKEMON:
                encoded.append(CHAR_TO_POKEMON[char])
            else:
                # Try to find similar character or use space
                encoded.append(0x00)

        # Add string terminator
        encoded.append(0xFF)
        return bytes(encoded)

    def encode_text(self, text, encoding):
        """Encode text based on encoding type."""
        if encoding == 'pokemon':
            return self.encode_pokemon_string(text)
        else:  # ascii
            return text.encode('ascii', errors='replace')

    def write_pointer(self, pointer_offset, target_offset):
        """Write a pointer at the given offset."""
        pointer_value = self.GBA_ROM_BASE + target_offset
        pointer_bytes = struct.pack('<I', pointer_value)
        self.rom_data[pointer_offset:pointer_offset+4] = pointer_bytes

    def translate_text(self, entry):
        """
        Translate a single text entry, relocating if necessary.

        Returns:
            (success, relocated, original_offset, new_offset)
        """
        offset = entry['offset']
        text = entry['text']
        original_length = entry['length']
        encoding = entry['encoding']

        # Encode the new text
        encoded = self.encode_text(text, encoding)
        new_length = len(encoded)

        # Check if it fits in place
        if new_length <= original_length:
            # Fits in place - direct replacement
            for i, byte in enumerate(encoded):
                self.rom_data[offset + i] = byte

            # Pad remaining space
            for i in range(new_length, original_length):
                self.rom_data[offset + i] = 0x00

            return (True, False, offset, offset)

        # Text is too long - need to relocate
        print(f"  Text at 0x{offset:08X} too long ({new_length} > {original_length})")

        # Find pointers to this offset
        pointers = self.find_pointers_to_offset(offset)

        if not pointers:
            print(f"  WARNING: No pointers found for 0x{offset:08X}, using direct write anyway")
            # Still try to write in place, truncating if necessary
            for i in range(min(new_length, original_length)):
                self.rom_data[offset + i] = encoded[i]
            return (True, False, offset, offset)

        # Relocate to free space
        new_offset = self.free_space_offset

        # Write new text to free space
        for i, byte in enumerate(encoded):
            self.rom_data[new_offset + i] = byte

        # Update all pointers
        for ptr_loc in pointers:
            self.write_pointer(ptr_loc, new_offset)
            self.pointer_updates[ptr_loc] = {
                'old_target': offset,
                'new_target': new_offset
            }

        print(f"  Relocated to 0x{new_offset:08X}, updated {len(pointers)} pointer(s)")

        # Track relocation
        self.relocated_texts.append({
            'original_offset': offset,
            'new_offset': new_offset,
            'text': text,
            'size': new_length,
            'pointers_updated': len(pointers)
        })

        # Advance free space pointer
        self.free_space_offset += new_length

        # Clear original location
        for i in range(original_length):
            self.rom_data[offset + i] = 0xFF

        return (True, True, offset, new_offset)

    def translate_all(self):
        """Translate all texts, relocating when necessary."""
        print("\nTranslating texts...")

        # Find free space first
        self.free_space_offset = self.find_free_space()

        success_count = 0
        relocated_count = 0
        error_count = 0

        for i, entry in enumerate(self.texts_data['texts']):
            try:
                success, relocated, old_off, new_off = self.translate_text(entry)

                if success:
                    success_count += 1
                    if relocated:
                        relocated_count += 1

                if (i + 1) % 1000 == 0:
                    print(f"  Progress: {i+1}/{len(self.texts_data['texts'])} texts processed")

            except Exception as e:
                print(f"  Error at offset 0x{entry['offset']:08X}: {e}")
                error_count += 1

        print(f"\nTranslation complete:")
        print(f"  Successfully translated: {success_count}")
        print(f"  Relocated texts: {relocated_count}")
        print(f"  Errors: {error_count}")
        print(f"  Free space used: {self.free_space_offset - self.find_free_space()} bytes")

    def save_rom(self, output_path):
        """Save translated ROM."""
        with open(output_path, 'wb') as f:
            f.write(self.rom_data)
        print(f"\nSaved translated ROM to: {output_path}")

    def save_relocation_report(self, output_path):
        """Save a report of all relocations."""
        report_data = {
            'relocated_count': len(self.relocated_texts),
            'pointers_updated': len(self.pointer_updates),
            'relocated_texts': self.relocated_texts,
            'pointer_updates': [
                {
                    'pointer_at': f'0x{ptr:08X}',
                    'old_target': f'0x{info["old_target"]:08X}',
                    'new_target': f'0x{info["new_target"]:08X}'
                }
                for ptr, info in self.pointer_updates.items()
            ]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        print(f"Saved relocation report to: {output_path}")


def main():
    if len(sys.argv) not in [3, 4]:
        print("Usage: python translate_rom.py <rom.gba> <translation.json> [output.gba]")
        print("\nThis script translates texts with automatic relocation for longer strings.")
        print("\nExample:")
        print("  python translate_rom.py englishrom.gba translation.json translated.gba")
        sys.exit(1)

    rom_file = sys.argv[1]
    json_file = sys.argv[2]

    if len(sys.argv) == 4:
        output_file = sys.argv[3]
    else:
        output_file = Path(rom_file).stem + "_translated.gba"

    # Verify files
    if not Path(rom_file).exists():
        print(f"Error: ROM file '{rom_file}' not found")
        sys.exit(1)

    if not Path(json_file).exists():
        print(f"Error: Translation file '{json_file}' not found")
        sys.exit(1)

    # Translate ROM
    translator = ROMTranslator(rom_file, json_file)
    translator.load_rom()
    translator.load_texts()
    translator.translate_all()
    translator.save_rom(output_file)

    # Save relocation report
    report_path = Path(output_file).with_suffix('.relocation_report.json')
    translator.save_relocation_report(report_path)

    print(f"\nTranslation complete!")
    print(f"Translated ROM: {output_file}")
    print(f"Relocation report: {report_path}")


if __name__ == "__main__":
    main()
