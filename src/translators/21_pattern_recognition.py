#!/usr/bin/env python3
"""
21 - Pattern recognition: Lookup tables or recurring encoding

Checks whether the 8 substitutions use a lookup table system
or an encoding that could be reproducible.
"""

import sys
import json
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def find_encoding_pattern():
    """Search for encoding patterns."""
    
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
    print("🔐 PATTERN RECOGNITION: Recurring encoding?")
    print("=" * 80)
    print()
    
    # Collect the 8 substitutions
    substitutions = []
    
    for failure in failures:
        offset = int(failure['offset'], 16)
        
        # Find terminator
        en_term = None
        es_term = None
        
        for j in range(offset, min(offset + 100, len(english_rom.rom_data))):
            if en_term is None and english_rom.rom_data[j] == 0x00:
                en_term = j - offset
            if es_term is None and spanish_rom.rom_data[j] == 0x00:
                es_term = j - offset
        
        if en_term == es_term and en_term is not None and en_term > 0:
            # Direct substitution
            en_bytes = english_rom.rom_data[offset:offset+en_term]
            es_bytes = spanish_rom.rom_data[offset:offset+es_term]
            
            substitutions.append({
                'offset': offset,
                'length': en_term,
                'en_bytes': en_bytes,
                'es_bytes': es_bytes,
                'en_text': failure['english_text'][:30],
                'es_text': failure['spanish_text'][:30],
            })
    
    print(f"📍 Analyzing {len(substitutions)} direct substitutions:\n")
    
    # For each substitution, search for a pattern
    all_mappings = Counter()
    byte_mappings = {}
    
    for sub in substitutions:
        print(f"Offset 0x{sub['offset']:08X} ({sub['length']} bytes)")
        print(f"  EN: {' '.join(f'{b:02x}' for b in sub['en_bytes'][:15])}")
        print(f"  ES: {' '.join(f'{b:02x}' for b in sub['es_bytes'][:15])}")
        
        # Create mapping: en_byte -> es_byte
        mappings = {}
        for i, (en_b, es_b) in enumerate(zip(sub['en_bytes'], sub['es_bytes'])):
            if en_b not in mappings:
                mappings[en_b] = es_b
            elif mappings[en_b] != es_b:
                # Conflict: the same English byte maps to two different Spanish bytes
                print(f"    ⚠️  Byte 0x{en_b:02X} → 0x{mappings[en_b]:02X} vs 0x{es_b:02X} (conflict!)")
                if en_b not in byte_mappings:
                    byte_mappings[en_b] = set()
                byte_mappings[en_b].add(es_b)
            else:
                all_mappings[(en_b, es_b)] += 1
        
        # Check if XOR is constant
        xor_vals = [en_b ^ es_b for en_b, es_b in zip(sub['en_bytes'], sub['es_bytes'])]
        if len(set(xor_vals)) == 1:
            print(f"    ✅ XOR CONSTANT: 0x{xor_vals[0]:02X}")
        else:
            print(f"    ❌ XOR varied: {set(xor_vals)}")
        
        print()
    
    print("=" * 80)
    print("GLOBAL ANALYSIS")
    print("=" * 80)
    print()
    
    print(f"Total unique byte mappings: {len(all_mappings)}")

    # Most frequent mappings
    print("\nTop 20 most frequent mappings:")
    for (en_b, es_b), count in all_mappings.most_common(20):
        print(f"  0x{en_b:02X} → 0x{es_b:02X}  ({count}x)")
    
    # Check if this is a true lookup table
    print()
    if all(en_b < 256 and es_b < 256 for en_b, es_b in all_mappings):
        print("💡 Hypothesis: The data might use a LOOKUP TABLE")
        print("    where each byte is consistently mapped to another byte")

        # Create a partial lookup table
        en_to_es_map = {}
        for (en_b, es_b), count in all_mappings.items():
            if en_b not in en_to_es_map:
                en_to_es_map[en_b] = es_b

        print(f"\n✅ Partial lookup table ({len(en_to_es_map)} entries):")
        for en_b in sorted(en_to_es_map.keys()):
            print(f"    0x{en_b:02X} → 0x{en_to_es_map[en_b]:02X}")


if __name__ == "__main__":
    find_encoding_pattern()
