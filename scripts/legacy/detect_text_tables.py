#!/usr/bin/env python3
"""
Advanced Text Table Detection for Pokemon GBA ROMs

This script detects and analyzes text pointer tables to enable
proper relocation of text arrays, not just individual texts.

Strategy:
1. Find all pointer tables in ROM
2. Identify which tables contain text pointers
3. Build a map: text_offset → table that references it
4. Enable relocation of entire tables
"""

import struct
import json
from pathlib import Path
from collections import defaultdict


class TextTable:
    """Represents a table of text pointers."""

    def __init__(self, table_offset, pointers):
        self.table_offset = table_offset
        self.pointers = pointers  # List of (index, rom_offset)
        self.num_entries = len(pointers)
        self.text_offsets = [offset for _, offset in pointers]

    def __repr__(self):
        return f"TextTable(offset=0x{self.table_offset:08X}, entries={self.num_entries})"


class TextTableDetector:
    """Detects text pointer tables in Pokemon GBA ROMs."""

    GBA_ROM_BASE = 0x08000000

    def __init__(self, rom_path):
        self.rom_path = Path(rom_path)
        self.rom_data = None
        self.rom_size = 0
        self.pointer_tables = []
        self.text_tables = []
        self.offset_to_table = {}  # Maps text offset to table

    def load_rom(self):
        """Load ROM into memory."""
        with open(self.rom_path, 'rb') as f:
            self.rom_data = f.read()
        self.rom_size = len(self.rom_data)
        print(f"Loaded ROM: {self.rom_path.name} ({self.rom_size} bytes)")

    def is_valid_rom_pointer(self, ptr_value):
        """Check if a value is a valid GBA ROM pointer."""
        if (ptr_value & 0xFF000000) != 0x08000000:
            return False

        rom_offset = ptr_value - self.GBA_ROM_BASE
        return 0 <= rom_offset < self.rom_size

    def read_pointer(self, offset):
        """Read a 32-bit little-endian pointer at offset."""
        if offset + 4 > self.rom_size:
            return None

        ptr_value = struct.unpack('<I', self.rom_data[offset:offset+4])[0]
        if self.is_valid_rom_pointer(ptr_value):
            return ptr_value - self.GBA_ROM_BASE
        return None

    def detect_pointer_tables(self, min_entries=5):
        """
        Detect all pointer tables in ROM.

        A pointer table is a sequence of consecutive valid ROM pointers.
        """
        print(f"\nDetecting pointer tables (min {min_entries} entries)...")
        tables = []

        i = 0
        while i < self.rom_size - 20:
            # Try to read consecutive pointers
            pointers = []
            offset = i

            while offset < self.rom_size - 4:
                rom_offset = self.read_pointer(offset)
                if rom_offset is not None:
                    pointers.append((len(pointers), rom_offset))
                    offset += 4
                else:
                    break

            # If we found enough pointers, it's likely a table
            if len(pointers) >= min_entries:
                table = TextTable(i, pointers)
                tables.append(table)
                i = offset  # Skip past this table
            else:
                i += 4

        self.pointer_tables = tables
        print(f"Found {len(tables)} pointer tables")
        return tables

    def is_text_pointer(self, rom_offset):
        """
        Check if an offset likely points to text.

        Heuristics:
        - Contains Pokemon encoding characters (0xBB-0xEE range)
        - Ends with 0xFF (Pokemon string terminator)
        - Reasonable length (4-200 chars)
        """
        if rom_offset + 4 > self.rom_size:
            return False

        # Check first 100 bytes for Pokemon patterns
        sample_size = min(100, self.rom_size - rom_offset)
        sample = self.rom_data[rom_offset:rom_offset + sample_size]

        # Count Pokemon encoding bytes
        pokemon_chars = sum(1 for b in sample if 0xBB <= b <= 0xEE or b in [0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xAB, 0xAC, 0xAD, 0xAE, 0xB8])

        # Look for string terminator
        has_terminator = 0xFF in sample

        # ASCII text check
        ascii_chars = sum(1 for b in sample if 0x20 <= b <= 0x7E)

        # Determine if it's text
        if pokemon_chars >= 4 and has_terminator:
            return True
        if ascii_chars >= 10 and (has_terminator or 0x00 in sample):
            return True

        return False

    def classify_tables(self):
        """
        Classify pointer tables as text tables or other.

        A table is a text table if majority of its pointers point to text.
        """
        print("\nClassifying pointer tables...")
        text_tables = []

        for table in self.pointer_tables:
            # Sample some pointers from the table
            sample_size = min(10, table.num_entries)
            samples = table.pointers[:sample_size]

            text_count = sum(1 for _, offset in samples if self.is_text_pointer(offset))
            text_ratio = text_count / sample_size

            if text_ratio >= 0.5:  # At least 50% point to text
                text_tables.append(table)

                # Build reverse mapping
                for _, text_offset in table.pointers:
                    if text_offset not in self.offset_to_table:
                        self.offset_to_table[text_offset] = []
                    self.offset_to_table[text_offset].append(table)

        self.text_tables = text_tables
        print(f"Identified {len(text_tables)} text tables")
        return text_tables

    def find_table_for_text(self, text_offset):
        """
        Find which table(s) reference a specific text offset.

        Returns: List of (table, index_in_table)
        """
        results = []

        if text_offset in self.offset_to_table:
            for table in self.offset_to_table[text_offset]:
                # Find index in table
                for idx, offset in table.pointers:
                    if offset == text_offset:
                        results.append((table, idx))
                        break

        return results

    def analyze_table(self, table, extract_texts=True):
        """
        Analyze a text table in detail.

        Returns dict with:
        - table_offset
        - num_entries
        - text_samples (if extract_texts)
        - total_text_size
        - text_offsets
        """
        info = {
            'table_offset': f'0x{table.table_offset:08X}',
            'num_entries': table.num_entries,
            'text_offsets': [f'0x{off:08X}' for off in table.text_offsets],
            'texts': []
        }

        if extract_texts:
            # Extract sample texts
            for i, (idx, offset) in enumerate(table.pointers[:10]):  # First 10 only
                text = self.extract_text_at_offset(offset)
                if text:
                    info['texts'].append({
                        'index': idx,
                        'offset': f'0x{offset:08X}',
                        'text': text[:50] + '...' if len(text) > 50 else text
                    })

        return info

    def extract_text_at_offset(self, offset):
        """Extract Pokemon-encoded text at offset."""
        POKEMON_CHARS = {
            0x00: ' ', 0xBB: 'A', 0xBC: 'B', 0xBD: 'C', 0xBE: 'D', 0xBF: 'E',
            0xC0: 'F', 0xC1: 'G', 0xC2: 'H', 0xC3: 'I', 0xC4: 'J', 0xC5: 'K',
            0xC6: 'L', 0xC7: 'M', 0xC8: 'N', 0xC9: 'O', 0xCA: 'P', 0xCB: 'Q',
            0xCC: 'R', 0xCD: 'S', 0xCE: 'T', 0xCF: 'U', 0xD0: 'V', 0xD1: 'W',
            0xD2: 'X', 0xD3: 'Y', 0xD4: 'Z', 0xD5: 'a', 0xD6: 'b', 0xD7: 'c',
            0xD8: 'd', 0xD9: 'e', 0xDA: 'f', 0xDB: 'g', 0xDC: 'h', 0xDD: 'i',
            0xDE: 'j', 0xDF: 'k', 0xE0: 'l', 0xE1: 'm', 0xE2: 'n', 0xE3: 'o',
            0xE4: 'p', 0xE5: 'q', 0xE6: 'r', 0xE7: 's', 0xE8: 't', 0xE9: 'u',
            0xEA: 'v', 0xEB: 'w', 0xEC: 'x', 0xED: 'y', 0xEE: 'z',
            0xA1: '0', 0xA2: '1', 0xA3: '2', 0xA4: '3', 0xA5: '4',
            0xA6: '5', 0xA7: '6', 0xA8: '7', 0xA9: '8', 0xAA: '9',
            0xAB: '!', 0xAC: '?', 0xAD: '.', 0xAE: '-', 0xB8: ',',
            0xFE: '\n'
        }

        if offset + 4 > self.rom_size:
            return None

        decoded = []
        i = offset
        max_len = 200

        while i < self.rom_size and len(decoded) < max_len:
            byte = self.rom_data[i]

            if byte == 0xFF:  # End of string
                break

            if byte in POKEMON_CHARS:
                decoded.append(POKEMON_CHARS[byte])
            else:
                # ASCII fallback
                if 0x20 <= byte <= 0x7E:
                    decoded.append(chr(byte))
                else:
                    decoded.append('.')

            i += 1

        return ''.join(decoded) if decoded else None

    def save_analysis(self, output_path):
        """Save analysis results to JSON."""
        analysis = {
            'rom_name': self.rom_path.name,
            'rom_size': self.rom_size,
            'total_pointer_tables': len(self.pointer_tables),
            'total_text_tables': len(self.text_tables),
            'text_tables': []
        }

        # Analyze each text table
        for table in self.text_tables[:50]:  # First 50 tables
            info = self.analyze_table(table)
            analysis['text_tables'].append(info)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)

        print(f"\nAnalysis saved to: {output_path}")

    def generate_report(self):
        """Generate human-readable report."""
        print("\n" + "="*80)
        print("TEXT TABLE DETECTION REPORT")
        print("="*80)
        print(f"ROM: {self.rom_path.name}")
        print(f"Size: {self.rom_size} bytes ({self.rom_size // (1024*1024)} MB)")
        print()

        print(f"Pointer tables found: {len(self.pointer_tables)}")
        print(f"Text tables identified: {len(self.text_tables)}")
        print(f"Unique text offsets: {len(self.offset_to_table)}")
        print()

        # Show largest text tables
        sorted_tables = sorted(self.text_tables, key=lambda t: t.num_entries, reverse=True)
        print("Top 10 Largest Text Tables:")
        print("-" * 80)
        for i, table in enumerate(sorted_tables[:10], 1):
            print(f"{i:2d}. Offset: 0x{table.table_offset:08X} | {table.num_entries:4d} entries")

            # Show sample texts
            samples = []
            for _, offset in table.pointers[:3]:
                text = self.extract_text_at_offset(offset)
                if text:
                    samples.append(text[:40])

            if samples:
                print(f"    Samples: {' | '.join(samples)}")

        print("="*80)


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python detect_text_tables.py <rom.gba> [output.json]")
        print("\nDetects and analyzes text pointer tables in GBA ROM.")
        print("\nExample:")
        print("  python detect_text_tables.py englishrom.gba text_tables.json")
        sys.exit(1)

    rom_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) >= 3 else 'text_tables_analysis.json'

    if not Path(rom_file).exists():
        print(f"Error: ROM file '{rom_file}' not found")
        sys.exit(1)

    # Detect tables
    detector = TextTableDetector(rom_file)
    detector.load_rom()
    detector.detect_pointer_tables(min_entries=5)
    detector.classify_tables()

    # Generate reports
    detector.generate_report()
    detector.save_analysis(output_file)

    # Test: Find table for a specific text
    print("\nTesting: Find table for text at 0x0023E5DA (Nurse)...")
    results = detector.find_table_for_text(0x0023E5DA)

    if results:
        for table, idx in results:
            print(f"  Found in table at 0x{table.table_offset:08X}, index {idx}")
            print(f"  Table has {table.num_entries} entries")
    else:
        print("  Not found in any detected table (might be sequential array)")


if __name__ == "__main__":
    main()
