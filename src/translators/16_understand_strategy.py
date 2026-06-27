#!/usr/bin/env python3
"""
16 - Understand the Spanish ROM strategy

Analyzes how the Spanish ROM handles overflows.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader
from src.core.padding_detector import PaddingDetector


def analyze_strategy():
    """Analyzes the strategy used by the Spanish ROM."""

    # Load the test report
    report_path = Path('output/tests/2026-01-14_spanish_simulation_report.json')
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)

    failures = report['failures']

    # Load the ROMs
    print("📖 Loading ROMs and diff_with_padding...")
    english_rom = ROMReader('input/roms/englishrom.gba')
    spanish_rom = ROMReader('input/roms/spanishrom.gba')
    english_rom.load()
    spanish_rom.load()

    # Load diff_with_padding
    with open('output/differences/2026-01-13_diff_with_padding.json', 'r', encoding='utf-8') as f:
        diff_data = json.load(f)

    # Build a dictionary of texts by offset
    texts_by_offset = {t['offset']: t for t in diff_data['texts']}

    print()
    print("=" * 80)
    print("SPANISH ROM STRATEGY - ANALYSIS OF 11 CASES")
    print("=" * 80)
    print()

    for i, failure in enumerate(failures, 1):
        offset = failure['offset']
        offset_int = int(offset, 16)

        print(f"\n{i}. Offset {offset}")
        print(f"   Type: {failure['category']} | Overflow: {failure['overflow']} bytes")

        # Find the reference text
        if offset_int in texts_by_offset:
            text_info = texts_by_offset[offset_int]
            print(f"   Padding info found:")
            print(f"   - Text: '{text_info['text'][:40]}...'")
            print(f"   - Encoding: {text_info['encoding']}")
            print(f"   - Padding: {text_info['padding_available']} bytes")
            print(f"   - Real max: {text_info['real_max_length']} bytes")

        # Analyze bytes before/after offset
        print(f"\n   Strategy detected:")

        # Extract context (30 bytes before and after)
        start = max(0, offset_int - 30)
        end = min(len(english_rom.rom_data), offset_int + 150)

        en_context = english_rom.rom_data[start:end]
        es_context = spanish_rom.rom_data[start:end]

        # Look for a reallocation pattern (changed pointers)
        has_pointer_changes = False
        has_relocation = False

        # Check for 0xFF padding patterns
        en_padding_count = sum(1 for j in range(start, min(end, offset_int + 50)) if english_rom.rom_data[j] == 0xFF)
        es_padding_count = sum(1 for j in range(start, min(end, offset_int + 50)) if spanish_rom.rom_data[j] == 0xFF)

        if en_padding_count != es_padding_count:
            print(f"   → Padding/separation modified")
            print(f"      EN: {en_padding_count} bytes 0xFF vs ES: {es_padding_count} bytes 0xFF")

        # Count identical bytes around the offset
        identical_before = sum(1 for j in range(max(start, offset_int-20), offset_int)
                              if english_rom.rom_data[j] == spanish_rom.rom_data[j])

        identical_after = sum(1 for j in range(offset_int, min(end, offset_int+20))
                             if english_rom.rom_data[j] == spanish_rom.rom_data[j])

        print(f"   → Similarity:")
        print(f"      Before offset: {identical_before}/20 identical bytes")
        print(f"      After offset: {identical_after}/20 identical bytes")

        if identical_before == 20 and identical_after < 15:
            print(f"   → This offset marks a STRUCTURAL CHANGE")
            print(f"      The text was probably RELOCATED in the ROM!")

        print()


if __name__ == "__main__":
    analyze_strategy()
