#!/usr/bin/env python3
"""
04 - Analyse Structurelle: Longueurs et Terminateurs

Analyse détaillée des 11 cas pour comprendre si ce sont:
- Des substitutions directes (longueur identique)
- Des relocalisations (longueurs différentes)

Scripts consolidés:
- 19_analyze_structure.py
- 20_discover_strategies.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def analyze_structure():
    """Analyse structurelle des textes."""
    
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
    print("🏗️ ANALYSE STRUCTURELLE: Classification substitution vs relocalisation")
    print("=" * 80)
    print()
    
    substitutions = []
    relocations = []
    
    for failure in failures:
        offset = int(failure['offset'], 16)
        
        # Trouver longueurs réelles
        en_term = None
        es_term = None
        
        for j in range(offset, min(offset + 100, len(english_rom.rom_data))):
            if en_term is None and english_rom.rom_data[j] == 0x00:
                en_term = j - offset
            if es_term is None and spanish_rom.rom_data[j] == 0x00:
                es_term = j - offset
        
        if en_term == es_term and en_term is not None:
            substitutions.append({
                'offset': offset,
                'length': en_term,
                'en_text': failure['english_text'][:40],
                'es_text': failure['spanish_text'][:40],
            })
        else:
            relocations.append({
                'offset': offset,
                'en_length': en_term,
                'es_length': es_term,
                'en_text': failure['english_text'][:40],
                'es_text': failure['spanish_text'][:40],
            })
    
    print(f"📊 RÉSULTATS:")
    print(f"   Substitutions directes (in-place): {len(substitutions)}")
    print(f"   Relocalisations (déplacées): {len(relocations)}")
    print()
    
    if substitutions:
        print("=" * 80)
        print("SUBSTITUTIONS DIRECTES (longueur préservée)")
        print("=" * 80)
        print()
        
        for i, sub in enumerate(substitutions, 1):
            print(f"{i}. 0x{sub['offset']:08X} ({sub['length']} bytes)")
            print(f"   EN: \"{sub['en_text']}...\"")
            print(f"   ES: \"{sub['es_text']}...\"")
            print()
    
    if relocations:
        print("=" * 80)
        print("RELOCALISATIONS (longueur variable)")
        print("=" * 80)
        print()
        
        for i, rel in enumerate(relocations, 1):
            print(f"{i}. 0x{rel['offset']:08X}")
            print(f"   EN length: {rel['en_length']} → ES length: {rel['es_length']}")
            print(f"   EN: \"{rel['en_text']}...\"")
            print(f"   ES: \"{rel['es_text']}...\"")
            print()


if __name__ == "__main__":
    analyze_structure()
