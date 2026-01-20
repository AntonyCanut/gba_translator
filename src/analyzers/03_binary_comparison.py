#!/usr/bin/env python3
"""
03 - Investigation Binaire: Analyse des 11 cas d'échec

Comparaison byte-by-byte entre ROM anglaise et espagnole
pour comprendre le mécanisme de substitution/relocalisation.

Scripts consolidés:
- 15_analyze_failures.py (analyse binaire)
- 16_understand_strategy.py (stratégie)
- 18_find_relocation.py (patterns)
"""

import sys
import json
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def analyze_binary_comparison():
    """Analyse binaire des 11 offsets d'échec."""
    
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
    print("📊 ANALYSE BINAIRE: Comparaison ROM anglaise vs espagnole")
    print("=" * 80)
    print()
    
    for i, failure in enumerate(failures, 1):
        offset = int(failure['offset'], 16)
        
        print(f"{i:2d}. Offset 0x{offset:08X}")
        print(f"    Catégorie: {failure['category']}")
        
        # Extraire contexte binaire
        start = max(0, offset - 16)
        end = min(len(english_rom.rom_data), offset + 50)
        
        en_data = english_rom.rom_data[start:end]
        es_data = spanish_rom.rom_data[start:end]
        
        marker = offset - start
        
        # Afficher comparaison
        en_hex = ' '.join(f'{b:02x}' for b in en_data)
        es_hex = ' '.join(f'{b:02x}' for b in es_data)
        
        print(f"    EN: ...{en_hex[:marker*3]}[{en_hex[marker*3:marker*3+2]}]...")
        print(f"    ES: ...{es_hex[:marker*3]}[{es_hex[marker*3:marker*3+2]}]...")
        
        # Analyser différences
        diffs = sum(1 for a, b in zip(en_data, es_data) if a != b)
        print(f"    → {diffs} bytes différents / {len(en_data)}")
        
        # Trouver terminateur NULL
        en_term = None
        es_term = None
        for j in range(offset, min(offset + 100, len(english_rom.rom_data))):
            if en_term is None and english_rom.rom_data[j] == 0x00:
                en_term = j - offset
            if es_term is None and spanish_rom.rom_data[j] == 0x00:
                es_term = j - offset
        
        if en_term == es_term:
            print(f"    ✅ Terminateur: +{en_term} bytes (SUBSTITUTION IN-PLACE)")
        else:
            print(f"    ⚠️ Terminateur: EN=+{en_term}, ES=+{es_term} (RELOCALISATION)")
        
        print()


if __name__ == "__main__":
    analyze_binary_comparison()
