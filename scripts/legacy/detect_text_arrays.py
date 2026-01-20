#!/usr/bin/env python3
"""
Advanced Text Array Detection for Pokemon GBA ROMs

This script detects sequential text arrays and finds the pointer tables
that reference them. This is the key to enabling full table relocation.

Strategy:
1. Find all sequential text arrays (clusters of texts)
2. Find all pointer tables in ROM
3. Match pointer tables to text arrays by checking if pointers
   point to the start offsets of texts in the arrays
4. Build complete map: array → table → pointer to table
"""

import struct
import json
from pathlib import Path
from collections import defaultdict


class TextArray:
    """Represents a sequential array of texts."""

    def __init__(self, texts, start_offset, end_offset):
        self.texts = texts  # List of text entries
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.size = end_offset - start_offset
        self.num_texts = len(texts)
        self.text_offsets = [t['offset'] for t in texts]

    def __repr__(self):
        return f"TextArray(start=0x{self.start_offset:08X}, texts={self.num_texts}, size={self.size})"


class PointerTable:
    """Represents a table of pointers."""

    def __init__(self, table_offset, pointers):
        self.table_offset = table_offset
        self.pointers = pointers  # List of rom_offsets
        self.num_entries = len(pointers)

    def __repr__(self):
        return f"PointerTable(offset=0x{self.table_offset:08X}, entries={self.num_entries})"


class TextArrayDetector:
    """Detects text arrays and their associated pointer tables."""

    GBA_ROM_BASE = 0x08000000

    def __init__(self, rom_path, differences_json):
        self.rom_path = Path(rom_path)
        self.differences_json = Path(differences_json)
        self.rom_data = None
        self.rom_size = 0

        self.text_arrays = []
        self.pointer_tables = []
        self.array_to_table = {}  # Maps array → tables that reference it
        self.table_to_pointer = {}  # Maps table → locations that point to it

    def load_rom(self):
        """Load ROM into memory."""
        with open(self.rom_path, 'rb') as f:
            self.rom_data = f.read()
        self.rom_size = len(self.rom_data)
        print(f"Loaded ROM: {self.rom_path.name} ({self.rom_size} bytes)")

    def load_differences(self):
        """Load difference texts."""
        with open(self.differences_json, 'r') as f:
            data = json.load(f)
        self.difference_texts = sorted(data['texts'], key=lambda t: t['offset'])
        print(f"Loaded {len(self.difference_texts)} difference texts")

    def detect_text_arrays(self, max_gap=100, min_cluster_size=3):
        """
        Detect sequential text arrays.

        Texts are considered part of the same array if they're within
        max_gap bytes of each other.
        """
        print(f"\nDetecting text arrays (max_gap={max_gap}, min_size={min_cluster_size})...")

        clusters = []
        current_cluster = [self.difference_texts[0]]

        for i in range(1, len(self.difference_texts)):
            prev_text = self.difference_texts[i-1]
            curr_text = self.difference_texts[i]

            # Calculate gap
            gap = curr_text['offset'] - (prev_text['offset'] + prev_text['length'])

            if gap < max_gap:
                current_cluster.append(curr_text)
            else:
                if len(current_cluster) >= min_cluster_size:
                    start = current_cluster[0]['offset']
                    end = current_cluster[-1]['offset'] + current_cluster[-1]['length']
                    clusters.append(TextArray(current_cluster, start, end))
                current_cluster = [curr_text]

        # Add last cluster
        if len(current_cluster) >= min_cluster_size:
            start = current_cluster[0]['offset']
            end = current_cluster[-1]['offset'] + current_cluster[-1]['length']
            clusters.append(TextArray(current_cluster, start, end))

        self.text_arrays = clusters
        print(f"Found {len(clusters)} text arrays")
        return clusters

    def is_valid_pointer(self, ptr_value):
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
        return ptr_value - self.GBA_ROM_BASE if self.is_valid_pointer(ptr_value) else None

    def detect_pointer_tables(self, min_entries=3, max_scan=0x02000000):
        """
        Detect all pointer tables in ROM.

        Limited to first max_scan bytes for performance.
        """
        print(f"\nDetecting pointer tables (min {min_entries} entries)...")
        tables = []

        i = 0
        scan_count = 0

        while i < min(self.rom_size - 20, max_scan):
            pointers = []
            offset = i

            while offset < self.rom_size - 4:
                rom_offset = self.read_pointer(offset)
                if rom_offset is not None:
                    pointers.append(rom_offset)
                    offset += 4
                else:
                    break

            if len(pointers) >= min_entries:
                table = PointerTable(i, pointers)
                tables.append(table)
                i = offset
                scan_count += 1

                if scan_count % 100 == 0:
                    print(f"  Scanned {scan_count} tables...", end='\r')
            else:
                i += 4

        self.pointer_tables = tables
        print(f"\nFound {len(tables)} pointer tables")
        return tables

    def match_tables_to_arrays(self):
        """
        Match pointer tables to text arrays.

        A table references an array if its pointers point to the start
        offsets of texts within the array.
        """
        print(f"\nMatching pointer tables to text arrays...")

        # Build quick lookup: text_offset → array
        offset_to_array = {}
        for array in self.text_arrays:
            for text in array.texts:
                offset_to_array[text['offset']] = array

        matches = 0

        for table in self.pointer_tables:
            # Check if this table's pointers point to texts in any array
            for ptr_offset in table.pointers[:20]:  # Sample first 20 pointers
                if ptr_offset in offset_to_array:
                    array = offset_to_array[ptr_offset]

                    # Add mapping
                    if array not in self.array_to_table:
                        self.array_to_table[array] = []

                    if table not in self.array_to_table[array]:
                        self.array_to_table[array].append(table)
                        matches += 1

        print(f"Found {matches} table → array connections")
        print(f"Arrays with pointer tables: {len(self.array_to_table)}/{len(self.text_arrays)}")

    def find_pointers_to_tables(self):
        """
        Find pointers that point to pointer tables.

        This is the final piece: finding what points to the tables themselves.
        """
        print(f"\nSearching for pointers to pointer tables...")

        # Get all table offsets we care about
        interesting_tables = set()
        for tables in self.array_to_table.values():
            interesting_tables.update(tables)

        print(f"Looking for pointers to {len(interesting_tables)} interesting tables...")

        # Search for pointers to these tables
        for table in interesting_tables:
            target_pointer = self.GBA_ROM_BASE + table.table_offset
            target_bytes = struct.pack('<I', target_pointer)

            pointers_found = []

            # Scan ROM for this pointer (aligned to 4 bytes)
            for i in range(0, min(self.rom_size - 3, 0x02000000), 4):
                if self.rom_data[i:i+4] == target_bytes:
                    pointers_found.append(i)

            if pointers_found:
                self.table_to_pointer[table] = pointers_found

        tables_with_pointers = len(self.table_to_pointer)
        print(f"Tables with pointers to them: {tables_with_pointers}/{len(interesting_tables)}")

    def generate_report(self):
        """Generate comprehensive report."""
        print("\n" + "="*80)
        print("TEXT ARRAY DETECTION REPORT")
        print("="*80)
        print(f"ROM: {self.rom_path.name}")
        print(f"Size: {self.rom_size} bytes ({self.rom_size // (1024*1024)} MB)")
        print()

        print(f"Text arrays found: {len(self.text_arrays)}")
        print(f"Pointer tables found: {len(self.pointer_tables)}")
        print(f"Arrays with pointer tables: {len(self.array_to_table)}")
        print(f"Tables with pointers to them: {len(self.table_to_pointer)}")
        print()

        # Show largest arrays
        sorted_arrays = sorted(self.text_arrays, key=lambda a: a.num_texts, reverse=True)
        print("Top 10 Largest Text Arrays:")
        print("-" * 80)

        for i, array in enumerate(sorted_arrays[:10], 1):
            print(f"\n{i}. Array at 0x{array.start_offset:08X}")
            print(f"   Texts: {array.num_texts} | Size: {array.size} bytes")
            print(f"   First text: \"{array.texts[0]['text'][:50]}\"")

            # Show associated tables
            if array in self.array_to_table:
                tables = self.array_to_table[array]
                print(f"   Pointer tables: {len(tables)}")

                for table in tables[:3]:  # Show first 3 tables
                    print(f"     - Table at 0x{table.table_offset:08X} ({table.num_entries} entries)")

                    # Show if we found pointers to this table
                    if table in self.table_to_pointer:
                        ptr_locations = self.table_to_pointer[table]
                        print(f"       Pointers to table: {len(ptr_locations)} at {[f'0x{p:08X}' for p in ptr_locations[:3]]}")
            else:
                print(f"   ⚠️  NO POINTER TABLE FOUND (sequential array)")

        print("\n" + "="*80)

        # Summary statistics
        arrays_with_full_chain = sum(
            1 for array in self.text_arrays
            if array in self.array_to_table and
            any(table in self.table_to_pointer for table in self.array_to_table[array])
        )

        print(f"\nRelocation capability:")
        print(f"  Arrays with full chain (array → table → pointer): {arrays_with_full_chain}")
        print(f"  Arrays with table only: {len(self.array_to_table) - arrays_with_full_chain}")
        print(f"  Arrays with no table: {len(self.text_arrays) - len(self.array_to_table)}")

        total_texts_in_arrays_with_chain = sum(
            array.num_texts for array in self.text_arrays
            if array in self.array_to_table and
            any(table in self.table_to_pointer for table in self.array_to_table[array])
        )

        total_texts = sum(array.num_texts for array in self.text_arrays)

        print(f"\n  Texts that can be relocated: {total_texts_in_arrays_with_chain}/{total_texts}")
        print(f"  Percentage: {100*total_texts_in_arrays_with_chain/total_texts:.1f}%")

        print("="*80)

    def save_analysis(self, output_path):
        """Save analysis to JSON."""
        analysis = {
            'rom_name': self.rom_path.name,
            'rom_size': self.rom_size,
            'text_arrays': [],
            'relocation_chains': []
        }

        # Save arrays
        for array in self.text_arrays[:100]:  # First 100 arrays
            array_info = {
                'start_offset': f'0x{array.start_offset:08X}',
                'end_offset': f'0x{array.end_offset:08X}',
                'num_texts': array.num_texts,
                'size': array.size,
                'first_text': array.texts[0]['text'][:50],
                'last_text': array.texts[-1]['text'][:50],
                'has_pointer_table': array in self.array_to_table
            }

            # Add table info if available
            if array in self.array_to_table:
                array_info['pointer_tables'] = [
                    {
                        'offset': f'0x{t.table_offset:08X}',
                        'entries': t.num_entries,
                        'has_pointers_to_it': t in self.table_to_pointer
                    }
                    for t in self.array_to_table[array]
                ]

            analysis['text_arrays'].append(array_info)

        # Save complete relocation chains
        for array in self.text_arrays:
            if array in self.array_to_table:
                for table in self.array_to_table[array]:
                    if table in self.table_to_pointer:
                        chain = {
                            'array_offset': f'0x{array.start_offset:08X}',
                            'array_size': array.num_texts,
                            'table_offset': f'0x{table.table_offset:08X}',
                            'table_entries': table.num_entries,
                            'pointer_locations': [f'0x{p:08X}' for p in self.table_to_pointer[table][:10]]
                        }
                        analysis['relocation_chains'].append(chain)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)

        print(f"\nAnalysis saved to: {output_path}")


def main():
    import sys

    if len(sys.argv) < 3:
        print("Usage: python detect_text_arrays.py <rom.gba> <differences.json> [output.json]")
        print("\nDetects text arrays and finds their pointer table chains.")
        print("\nExample:")
        print("  python detect_text_arrays.py englishrom.gba differences/englishrom_diff_only.json arrays.json")
        sys.exit(1)

    rom_file = sys.argv[1]
    diff_file = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) >= 4 else 'text_arrays_analysis.json'

    if not Path(rom_file).exists():
        print(f"Error: ROM file '{rom_file}' not found")
        sys.exit(1)

    if not Path(diff_file).exists():
        print(f"Error: Differences file '{diff_file}' not found")
        sys.exit(1)

    # Detect arrays and build chains
    detector = TextArrayDetector(rom_file, diff_file)
    detector.load_rom()
    detector.load_differences()
    detector.detect_text_arrays()
    detector.detect_pointer_tables()
    detector.match_tables_to_arrays()
    detector.find_pointers_to_tables()

    # Generate reports
    detector.generate_report()
    detector.save_analysis(output_file)


if __name__ == "__main__":
    main()
