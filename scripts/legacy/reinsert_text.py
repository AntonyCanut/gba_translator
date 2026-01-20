#!/usr/bin/env python3
"""
GBA ROM Text Reinsertion Tool
Reinserts modified text strings back into GBA ROM files.
"""

import sys
import json
import shutil
from pathlib import Path


class GBATextReinserter:
    def __init__(self, rom_path, json_path):
        self.rom_path = Path(rom_path)
        self.json_path = Path(json_path)
        self.rom_data = bytearray()
        self.texts_data = None

    def load_rom(self):
        """Load the ROM file into memory."""
        with open(self.rom_path, 'rb') as f:
            self.rom_data = bytearray(f.read())
        print(f"Loaded ROM: {self.rom_path.name} ({len(self.rom_data)} bytes)")

    def load_texts(self):
        """Load the modified text data from JSON."""
        with open(self.json_path, 'r', encoding='utf-8') as f:
            self.texts_data = json.load(f)
        print(f"Loaded {self.texts_data['text_count']} text entries from {self.json_path.name}")

    def encode_pokemon_string(self, text):
        """
        Encode a string using Pokemon character table.
        Returns bytes ready to be inserted into ROM.
        """
        # Pokemon character table (inverse of extraction table)
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
            '\n': 0xFE
        }

        encoded = bytearray()
        for char in text:
            if char in CHAR_TO_POKEMON:
                encoded.append(CHAR_TO_POKEMON[char])
            else:
                # Unknown character, use space
                print(f"Warning: Unknown character '{char}', replacing with space")
                encoded.append(0x00)

        # Add string terminator
        encoded.append(0xFF)

        return bytes(encoded)

    def encode_ascii_string(self, text):
        """Encode ASCII string."""
        return text.encode('ascii', errors='replace')

    def reinsert_text(self, entry):
        """Reinsert a single text entry into the ROM."""
        offset = entry['offset']
        text = entry['text']
        original_length = entry['length']
        encoding = entry['encoding']

        # Encode the text based on its type
        if encoding == 'pokemon':
            encoded = self.encode_pokemon_string(text)
        else:  # ascii
            encoded = self.encode_ascii_string(text)

        new_length = len(encoded)

        # Check if new text fits in original space
        if new_length > original_length:
            print(f"Warning: Text at 0x{offset:08X} is longer than original "
                  f"({new_length} > {original_length}). Truncating.")
            encoded = encoded[:original_length]
            new_length = original_length

        # Write the new text
        for i, byte in enumerate(encoded):
            if offset + i < len(self.rom_data):
                self.rom_data[offset + i] = byte

        # If new text is shorter, fill remaining space with padding
        if new_length < original_length:
            padding = original_length - new_length
            for i in range(padding):
                if offset + new_length + i < len(self.rom_data):
                    self.rom_data[offset + new_length + i] = 0x00

    def reinsert_all(self):
        """Reinsert all modified texts."""
        print("Reinserting texts...")
        success_count = 0
        error_count = 0

        for entry in self.texts_data['texts']:
            try:
                self.reinsert_text(entry)
                success_count += 1
            except Exception as e:
                print(f"Error at offset 0x{entry['offset']:08X}: {e}")
                error_count += 1

        print(f"Reinserted {success_count} texts successfully")
        if error_count > 0:
            print(f"Failed to reinsert {error_count} texts")

    def save_rom(self, output_path):
        """Save the modified ROM to a new file."""
        with open(output_path, 'wb') as f:
            f.write(self.rom_data)
        print(f"Saved modified ROM to {output_path}")

    def create_backup(self):
        """Create a backup of the original ROM."""
        backup_path = self.rom_path.with_suffix('.gba.bak')
        if not backup_path.exists():
            shutil.copy2(self.rom_path, backup_path)
            print(f"Created backup: {backup_path}")
        else:
            print(f"Backup already exists: {backup_path}")


def main():
    if len(sys.argv) not in [3, 4]:
        print("Usage: python reinsert_text.py <rom_file.gba> <texts.json> [output.gba]")
        print("  If output.gba is not specified, will create <rom_file>_modified.gba")
        sys.exit(1)

    rom_file = sys.argv[1]
    json_file = sys.argv[2]

    if len(sys.argv) == 4:
        output_file = sys.argv[3]
    else:
        output_file = Path(rom_file).stem + "_modified.gba"

    # Verify files exist
    if not Path(rom_file).exists():
        print(f"Error: ROM file '{rom_file}' not found")
        sys.exit(1)

    if not Path(json_file).exists():
        print(f"Error: JSON file '{json_file}' not found")
        sys.exit(1)

    # Reinsert texts
    reinserter = GBATextReinserter(rom_file, json_file)

    print("Creating backup...")
    reinserter.create_backup()

    reinserter.load_rom()
    reinserter.load_texts()
    reinserter.reinsert_all()
    reinserter.save_rom(output_file)

    print(f"\nReinsertion complete!")
    print(f"Modified ROM: {output_file}")


if __name__ == "__main__":
    main()
