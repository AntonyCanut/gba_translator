#!/usr/bin/env python3
"""
19 - Analyse structurelle: Indices vs données directes

Hypothèse: Les 11 cas d'échec utilisent peut-être un système d'INDIRECTION
via des indices plutôt que des données directes.
"""

import sys
import json
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def analyze_structure():
    """Analyse la structure des données autour des 11 offsets."""
    
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
    print("🔬 ANALYSE STRUCTURELLE: Indices vs Données Directes")
    print("=" * 80)
    print()
    
    print("Observation clé: Les bytes à l'offset sont IDENTIQUES")
    print("                Mais les données SUIVANTES sont DIFFÉRENTES")
    print()
    print("Cela suggère: Peut-être que l'INDICE/CODE est le même,")
    print("              mais l'implémentation diffère")
    print()
    
    # Pour chaque cas échoué
    for i, failure in enumerate(failures, 1):
        offset = int(failure['offset'], 16)
        
        en_byte = english_rom.rom_data[offset]
        es_byte = spanish_rom.rom_data[offset]
        
        # Chercher le terminateur NULL
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
        print(f"    Byte à offset: EN=0x{en_byte:02X}, ES=0x{es_byte:02X}")
        print(f"    Terminateur (distance): EN=+{en_term or '?'}, ES=+{es_term or '?'}")
        
        # Analyser la structure
        if en_term and es_term:
            if en_term == es_term:
                print(f"    → Même longueur! Peut-être une SUBSTITUTION directe")
            else:
                print(f"    → Longueurs DIFFÉRENTES: {en_term} vs {es_term}")
        
        # Extraire et comparer les séquences
        en_seq = english_rom.rom_data[offset:offset + (en_term or 20)]
        es_seq = spanish_rom.rom_data[offset:offset + (es_term or 20)]
        
        if en_seq == es_seq:
            print(f"    ✅ Les séquences sont IDENTIQUES!")
        else:
            # Compter les différences
            diffs = sum(1 for a, b in zip(en_seq, es_seq) if a != b)
            print(f"    ❌ Les séquences diffèrent à {diffs} positions")
        
        print()


if __name__ == "__main__":
    analyze_structure()
