#!/usr/bin/env python3
"""
GBA ROM Text Extractor
Extracts all readable text strings from GBA ROM files.
"""

import sys
import re
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core.text_codec import TextDecoder


class GBATextExtractor:
    def __init__(self, rom_path):
        self.rom_path = Path(rom_path)
        self.rom_data = None
        self.texts = []

    def load_rom(self):
        """Load the ROM file into memory."""
        with open(self.rom_path, 'rb') as f:
            self.rom_data = f.read()
        print(f"Loaded ROM: {self.rom_path.name} ({len(self.rom_data)} bytes)")

    def extract_ascii_strings(self, min_length=4):
        """Extract ASCII strings from ROM."""
        pattern = re.compile(b'[\x20-\x7E]{%d,}' % min_length)
        matches = pattern.finditer(self.rom_data)

        for match in matches:
            offset = match.start()
            text = match.group().decode('ascii', errors='ignore')
            self.texts.append({
                'offset': offset,
                'text': text,
                'length': len(text),
                'encoding': 'ascii'
            })

    def extract_pokemon_strings(self):
        """
        Extract Pokemon-specific encoded strings.
        Pokemon GBA games use a custom character table.
        Common patterns: 0xFF = end of string, 0xFE = newline
        """
        # Shared Pokemon table (byte -> char) from core\n        POKEMON_CHAR_TABLE = TextDecoder.POKEMON_DECODE

        i = 0
        while i < len(self.rom_data) - 4:
            # Look for potential text strings (starts with valid Pokemon chars)
            if self.rom_data[i] in POKEMON_CHAR_TABLE:
                start = i
                decoded = []
                length = 0

                # Try to decode a string
                while i < len(self.rom_data) and length < 1000:
                    byte = self.rom_data[i]

                    if byte == 0xFF:  # End of string
                        if len(decoded) >= 4:  # Minimum string length
                            text = ''.join(decoded)
                            if text.strip():  # Not just whitespace
                                self.texts.append({
                                    'offset': start,
                                    'text': text,
                                    'length': length,
                                    'encoding': 'pokemon'
                                })
                        break

                    if byte in POKEMON_CHAR_TABLE:
                        decoded.append(POKEMON_CHAR_TABLE[byte])
                        length += 1
                        i += 1
                    else:
                        # Invalid character, not a valid string
                        break

            i += 1

    def save_to_json(self, output_path):
        """Save extracted texts to JSON file."""
        output_data = {
            'rom_name': self.rom_path.name,
            'rom_size': len(self.rom_data),
            'text_count': len(self.texts),
            'texts': self.texts
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"Extracted {len(self.texts)} text strings to {output_path}")

    def save_to_txt(self, output_path):
        """Save extracted texts to readable TXT file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"ROM: {self.rom_path.name}\n")
            f.write(f"Total strings: {len(self.texts)}\n")
            f.write("=" * 80 + "\n\n")

            for entry in self.texts:
                f.write(f"Offset: 0x{entry['offset']:08X} | ")
                f.write(f"Length: {entry['length']} | ")
                f.write(f"Encoding: {entry['encoding']}\n")
                f.write(f"Text: {entry['text']}\n")
                f.write("-" * 80 + "\n")

        print(f"Created readable text file: {output_path}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python extract_text.py <rom_file.gba>")
        sys.exit(1)

    rom_file = sys.argv[1]

    if not Path(rom_file).exists():
        print(f"Error: ROM file '{rom_file}' not found")
        sys.exit(1)

    # Create output directory
    output_dir = Path('extracted_texts')
    output_dir.mkdir(exist_ok=True)

    # Extract texts
    extractor = GBATextExtractor(rom_file)
    extractor.load_rom()

    print("Extracting ASCII strings...")
    extractor.extract_ascii_strings(min_length=4)

    print("Extracting Pokemon-encoded strings...")
    extractor.extract_pokemon_strings()

    # Remove duplicates while preserving order and offset
    seen = set()
    unique_texts = []
    for entry in extractor.texts:
        key = (entry['offset'], entry['text'])
        if key not in seen:
            seen.add(key)
            unique_texts.append(entry)

    extractor.texts = sorted(unique_texts, key=lambda x: x['offset'])

    # Save outputs
    rom_name = Path(rom_file).stem
    json_output = output_dir / f"{rom_name}_texts.json"
    txt_output = output_dir / f"{rom_name}_texts.txt"

    extractor.save_to_json(json_output)
    extractor.save_to_txt(txt_output)

    print(f"\nExtraction complete!")
    print(f"JSON: {json_output}")
    print(f"TXT: {txt_output}")


if __name__ == "__main__":
    main()
