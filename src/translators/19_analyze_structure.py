#!/usr/bin/env python3
"""
19 - Structural analysis: Indices vs direct data

Hypothesis: The 11 failure cases may use an INDIRECTION system
via indices rather than direct data.
"""

import sys
import json
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def analyze_structure():
    """Analyzes the data structure around the 11 offsets."""
    
    report_path = Path('output/tests/2026-01-14_spanish_simulation_report.json')
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    failures = report['failures']
    
    english_rom = ROMReader('input/roms/englishrom.gba')
    spanish_rom = ROMReader('input/roms/spanishrom.gba')
    english_rom.load()
    spanish_rom.load()
    
    print()
    print("=" * 80)
    print("🔬 STRUCTURAL ANALYSIS: Indices vs Direct Data")
    print("=" * 80)
    print()
    
    print("Key observation: The bytes at the offset are IDENTICAL")
    print("                But the FOLLOWING data is DIFFERENT")
    print()
    print("This suggests: Perhaps the INDEX/CODE is the same,")
    print("               but the implementation differs")
    print()
    
    # For each failed case
    for i, failure in enumerate(failures, 1):
        offset = int(failure['offset'], 16)

        en_byte = english_rom.rom_data[offset]
        es_byte = spanish_rom.rom_data[offset]

        # Search for the NULL terminator
        en_term = None
        es_term = None

        for j in range(offset, min(offset + 100, len(english_rom.rom_data))):
            if en_term is None and english_rom.rom_data[j] == 0x00:
                en_term = j - offset
            if es_term is None and spanish_rom.rom_data[j] == 0x00:
                es_term = j - offset
            if en_term is not None and es_term is not None:
                break

        print(f"{i:2d}. 0x{offset:08X}")
        print(f"    Byte at offset: EN=0x{en_byte:02X}, ES=0x{es_byte:02X}")
        print(f"    Terminator (distance): EN=+{en_term or '?'}, ES=+{es_term or '?'}")

        # Analyze the structure
        if en_term and es_term:
            if en_term == es_term:
                print(f"    → Same length! Perhaps a direct SUBSTITUTION")
            else:
                print(f"    → DIFFERENT lengths: {en_term} vs {es_term}")

        # Extract and compare sequences
        en_seq = english_rom.rom_data[offset:offset + (en_term or 20)]
        es_seq = spanish_rom.rom_data[offset:offset + (es_term or 20)]

        if en_seq == es_seq:
            print(f"    ✅ Sequences are IDENTICAL!")
        else:
            # Count differences
            diffs = sum(1 for a, b in zip(en_seq, es_seq) if a != b)
            print(f"    ❌ Sequences differ at {diffs} positions")
        
        print()


if __name__ == "__main__":
    analyze_structure()
