#!/usr/bin/env python3
"""
15 - Analyze the 11 failure cases

Understand why the Spanish ROM works despite the detected overflows.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def analyze_failures():
    """Analyzes the 11 failure cases."""

    # Load the test report
    report_path = Path('output/tests/2026-01-14_spanish_simulation_report.json')
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)

    failures = report['failures']

    # Load the ROMs
    print("📖 Loading ROMs...")
    english_rom = ROMReader('input/roms/englishrom.gba')
    spanish_rom = ROMReader('input/roms/spanishrom.gba')
    english_rom.load()
    spanish_rom.load()

    print()
    print("=" * 80)
    print("ANALYSIS OF 11 FAILURE CASES")
    print("=" * 80)
    print()

    for i, failure in enumerate(failures, 1):
        offset = int(failure['offset'], 16)

        print(f"\n{i}. Offset 0x{offset:08X}")
        print(f"   Category: {failure['category']}")
        print(f"   Overflow: {failure['overflow']} bytes")
        print()

        # Extract binary context (16 bytes before and 50 after)
        start = max(0, offset - 16)
        end = min(len(english_rom.rom_data), offset + 100)

        # Display in hexadecimal
        print("   ENGLISH ROM (hexadecimal):")
        context_en = english_rom.rom_data[start:end]
        hex_str = ' '.join(f'{b:02x}' for b in context_en)

        # Mark the offset
        marker_pos = offset - start
        print(f"   {hex_str[:marker_pos*3]}[{hex_str[marker_pos*3:marker_pos*3+2]}]{hex_str[marker_pos*3+2:]}")
        print()

        print("   SPANISH ROM (hexadecimal):")
        context_es = spanish_rom.rom_data[start:end]
        hex_str_es = ' '.join(f'{b:02x}' for b in context_es)
        print(f"   {hex_str_es[:marker_pos*3]}[{hex_str_es[marker_pos*3:marker_pos*3+2]}]{hex_str_es[marker_pos*3+2:]}")
        print()

        # Check if data is identical
        if context_en == context_es:
            print("   ✅ ENGLISH and SPANISH data are IDENTICAL at this offset")
            print("   => This is padding/noise, not valid text!")
        else:
            print("   ❌ Data is DIFFERENT")
            # Count differences
            diffs = sum(1 for a, b in zip(context_en, context_es) if a != b)
            print(f"   {diffs} different bytes out of {len(context_en)}")

        print()

    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print()


if __name__ == "__main__":
    analyze_failures()
