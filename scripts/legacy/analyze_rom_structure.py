#!/usr/bin/env python3
"""
Analyze GBA ROM structure to understand text storage and pointer system.
"""

import struct
from pathlib import Path
from collections import defaultdict


class ROMAnalyzer:
    def __init__(self, rom_path):
        self.rom_path = Path(rom_path)
        self.rom_data = None
        self.load_rom()

    def load_rom(self):
        """Load ROM into memory."""
        with open(self.rom_path, 'rb') as f:
            self.rom_data = f.read()
        print(f"Loaded ROM: {self.rom_path.name} ({len(self.rom_data)} bytes)")

    def find_free_space(self, min_size=1024):
        """
        Find free space blocks in ROM (typically 0xFF padding).

        Args:
            min_size: Minimum size of free block to report

        Returns:
            List of (offset, size) tuples
        """
        free_blocks = []
        in_free_block = False
        block_start = 0

        print(f"\nScanning for free space blocks (min {min_size} bytes)...")

        for i in range(len(self.rom_data)):
            if self.rom_data[i] == 0xFF:
                if not in_free_block:
                    in_free_block = True
                    block_start = i
            else:
                if in_free_block:
                    block_size = i - block_start
                    if block_size >= min_size:
                        free_blocks.append((block_start, block_size))
                    in_free_block = False

        # Check if we ended in a free block
        if in_free_block:
            block_size = len(self.rom_data) - block_start
            if block_size >= min_size:
                free_blocks.append((block_start, block_size))

        return free_blocks

    def find_pointers_to_offset(self, target_offset, search_range=None):
        """
        Find pointers that reference a specific offset.
        GBA uses 32-bit little-endian pointers with base 0x08000000.

        Args:
            target_offset: ROM offset to search for
            search_range: Tuple (start, end) to limit search, or None for full ROM

        Returns:
            List of pointer locations
        """
        # GBA ROM is mapped to 0x08000000 in memory
        GBA_ROM_BASE = 0x08000000
        target_pointer = GBA_ROM_BASE + target_offset

        # Convert to little-endian bytes
        target_bytes = struct.pack('<I', target_pointer)

        pointers = []
        start = search_range[0] if search_range else 0
        end = search_range[1] if search_range else len(self.rom_data)

        i = start
        while i < end - 3:
            if self.rom_data[i:i+4] == target_bytes:
                pointers.append(i)
                i += 4  # Skip past this pointer
            else:
                i += 1

        return pointers

    def analyze_text_region(self, offset, length=100):
        """
        Analyze the region around a text offset to understand its structure.
        """
        start = max(0, offset - 50)
        end = min(len(self.rom_data), offset + length + 50)

        print(f"\nAnalyzing region around 0x{offset:08X}:")
        print(f"Range: 0x{start:08X} - 0x{end:08X}")

        # Look for pointers to this offset
        pointers = self.find_pointers_to_offset(offset)
        if pointers:
            print(f"Found {len(pointers)} pointer(s) to this offset:")
            for ptr_loc in pointers[:10]:  # Show first 10
                print(f"  Pointer at: 0x{ptr_loc:08X}")
        else:
            print("No pointers found to this offset (might be in a text array)")

        # Show hex dump
        print("\nHex dump (50 bytes before and after):")
        for i in range(start, end, 16):
            hex_part = ' '.join(f'{b:02X}' for b in self.rom_data[i:i+16])
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in self.rom_data[i:i+16])
            marker = ' <--' if i <= offset < i + 16 else ''
            print(f"  0x{i:08X}: {hex_part:48s} | {ascii_part}{marker}")

    def find_text_tables(self):
        """
        Find potential text pointer tables.
        These are sequences of pointers that point to text data.
        """
        GBA_ROM_BASE = 0x08000000
        potential_tables = []

        print("\nSearching for text pointer tables...")

        i = 0
        while i < len(self.rom_data) - 16:
            # Check if we have a sequence of valid ROM pointers
            consecutive_pointers = 0
            table_start = i

            while i < len(self.rom_data) - 3:
                ptr_value = struct.unpack('<I', self.rom_data[i:i+4])[0]

                # Check if it's a valid ROM pointer
                if (ptr_value & 0xFF000000) == 0x08000000:
                    rom_offset = ptr_value - GBA_ROM_BASE
                    if 0 <= rom_offset < len(self.rom_data):
                        consecutive_pointers += 1
                        i += 4
                        continue

                break

            # If we found at least 10 consecutive pointers, it's likely a table
            if consecutive_pointers >= 10:
                potential_tables.append((table_start, consecutive_pointers))
                print(f"  Found table at 0x{table_start:08X} with {consecutive_pointers} pointers")
            else:
                i = table_start + 4

        return potential_tables

    def get_rom_info(self):
        """Get basic ROM information."""
        if len(self.rom_data) >= 0xA0:
            title = self.rom_data[0xA0:0xAC].decode('ascii', errors='ignore')
            game_code = self.rom_data[0xAC:0xB0].decode('ascii', errors='ignore')
            maker_code = self.rom_data[0xB0:0xB2].decode('ascii', errors='ignore')

            print("\n" + "="*80)
            print("ROM Information")
            print("="*80)
            print(f"Title: {title}")
            print(f"Game Code: {game_code}")
            print(f"Maker Code: {maker_code}")
            print(f"ROM Size: {len(self.rom_data)} bytes ({len(self.rom_data) // (1024*1024)} MB)")
            print("="*80)


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python analyze_rom_structure.py <rom.gba> [text_offset]")
        print("\nExamples:")
        print("  python analyze_rom_structure.py englishrom.gba")
        print("  python analyze_rom_structure.py englishrom.gba 0x0018D42A")
        sys.exit(1)

    rom_file = sys.argv[1]

    analyzer = ROMAnalyzer(rom_file)
    analyzer.get_rom_info()

    # Find free space
    free_blocks = analyzer.find_free_space(min_size=10000)
    print(f"\nFound {len(free_blocks)} free space blocks (>10KB):")
    total_free = sum(size for _, size in free_blocks)
    print(f"Total free space: {total_free} bytes ({total_free // 1024} KB)")

    # Show largest blocks
    free_blocks.sort(key=lambda x: x[1], reverse=True)
    print("\nLargest free blocks:")
    for offset, size in free_blocks[:10]:
        print(f"  0x{offset:08X}: {size:8d} bytes ({size // 1024:5d} KB)")

    # Find text tables
    tables = analyzer.find_text_tables()

    # If a specific offset was provided, analyze it
    if len(sys.argv) >= 3:
        offset_str = sys.argv[2]
        if offset_str.startswith('0x'):
            offset = int(offset_str, 16)
        else:
            offset = int(offset_str)

        analyzer.analyze_text_region(offset)


if __name__ == "__main__":
    main()
