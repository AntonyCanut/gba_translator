#!/usr/bin/env python3
"""
05 - Reconnaissance de Patterns: Encodage et Byte Mappings

Cherche des patterns récurrents dans les données pour identifier
si un système de lookup table ou d'encodage alternatif est utilisé.

Scripts consolidés:
- 21_pattern_recognition.py
- 22_locate_lookup_table.py
"""

import sys
import json
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def analyze_patterns():
    """Analyse les patterns d'encodage."""
    
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
    print("🔐 RECONNAISSANCE DE PATTERNS: Encodage et Lookup Tables")
    print("=" * 80)
    print()
    
    # Collecter les substitutions directes
    substitutions = []
    for failure in failures:
        offset = int(failure['offset'], 16)
        
        en_term = None
        es_term = None
        
        for j in range(offset, min(offset + 100, len(english_rom.rom_data))):
            if en_term is None and english_rom.rom_data[j] == 0x00:
                en_term = j - offset
            if es_term is None and spanish_rom.rom_data[j] == 0x00:
                es_term = j - offset
        
        if en_term == es_term and en_term is not None and en_term > 0:
            en_bytes = english_rom.rom_data[offset:offset+en_term]
            es_bytes = spanish_rom.rom_data[offset:offset+es_term]
            
            substitutions.append({
                'offset': offset,
                'length': en_term,
                'en_bytes': en_bytes,
                'es_bytes': es_bytes,
            })
    
    print(f"Analysant {len(substitutions)} substitutions directes:\n")
    
    # Analyser byte mappings
    all_mappings = Counter()
    
    for sub in substitutions:
        for en_b, es_b in zip(sub['en_bytes'], sub['es_bytes']):
            all_mappings[(en_b, es_b)] += 1
    
    print(f"📊 Total mappings uniques: {len(all_mappings)}")
    print(f"\nTop 20 des byte-mappings les plus fréquents:")
    
    for (en_b, es_b), count in all_mappings.most_common(20):
        status = "✅" if en_b == es_b else "⚠️"
        print(f"  {status} 0x{en_b:02X} → 0x{es_b:02X}  ({count}x)")
    
    print()
    print("=" * 80)
    print("DÉTECTION DE PATTERNS")
    print("=" * 80)
    print()
    
    # Chercher XOR constant
    for i, sub in enumerate(substitutions[:5]):
        xor_vals = [en_b ^ es_b for en_b, es_b in zip(sub['en_bytes'], sub['es_bytes'])]
        if len(set(xor_vals)) == 1:
            print(f"✅ Offset 0x{sub['offset']:08X}: XOR constant 0x{xor_vals[0]:02X}")
        else:
            print(f"❌ Offset 0x{sub['offset']:08X}: XOR varié {set(xor_vals)}")
    
    print()
    print("=" * 80)
    print("OCCURENCES DE BYTES CLÉS")
    print("=" * 80)
    print()
    
    # Analyser byte 0x17 (anomalie détectée)
    common_bytes = [0x66, 0xBB, 0x33, 0xAA, 0x70, 0x88, 0x77, 0x11, 0x17, 0x71, 0xEE]
    
    for byte_val in common_bytes:
        en_count = english_rom.rom_data.count(bytes([byte_val]))
        es_count = spanish_rom.rom_data.count(bytes([byte_val]))
        diff = es_count - en_count
        
        if diff != 0:
            status = "📈" if diff > 0 else "📉"
            print(f"{status} 0x{byte_val:02X}: EN={en_count:,}, ES={es_count:,} (Δ = {diff:+,})")


if __name__ == "__main__":
    analyze_patterns()
