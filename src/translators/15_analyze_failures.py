#!/usr/bin/env python3
"""
15 - Analyser les 11 cas d'échec

Comprendre pourquoi la ROM espagnole fonctionne malgré les débordements détectés.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def analyze_failures():
    """Analyse les 11 cas d'échec."""
    
    # Charger le rapport de tests
    report_path = Path('output/tests/2026-01-14_spanish_simulation_report.json')
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    failures = report['failures']
    
    # Charger les ROMs
    print("📖 Chargement des ROMs...")
    english_rom = ROMReader('input/roms/englishrom.gba')
    spanish_rom = ROMReader('input/roms/spanishrom.gba')
    english_rom.load()
    spanish_rom.load()
    
    print()
    print("=" * 80)
    print("ANALYSE DES 11 CAS D'ÉCHEC")
    print("=" * 80)
    print()
    
    for i, failure in enumerate(failures, 1):
        offset = int(failure['offset'], 16)
        
        print(f"\n{i}. Offset 0x{offset:08X}")
        print(f"   Catégorie: {failure['category']}")
        print(f"   Débordement: {failure['overflow']} bytes")
        print()
        
        # Extraire contexte binaire (16 bytes avant et 50 après)
        start = max(0, offset - 16)
        end = min(len(english_rom.rom_data), offset + 100)
        
        # Afficher en hexadécimal
        print("   ENGLISH ROM (hexadécimal):")
        context_en = english_rom.rom_data[start:end]
        hex_str = ' '.join(f'{b:02x}' for b in context_en)
        
        # Marquer l'offset
        marker_pos = offset - start
        print(f"   {hex_str[:marker_pos*3]}[{hex_str[marker_pos*3:marker_pos*3+2]}]{hex_str[marker_pos*3+2:]}")
        print()
        
        print("   SPANISH ROM (hexadécimal):")
        context_es = spanish_rom.rom_data[start:end]
        hex_str_es = ' '.join(f'{b:02x}' for b in context_es)
        print(f"   {hex_str_es[:marker_pos*3]}[{hex_str_es[marker_pos*3:marker_pos*3+2]}]{hex_str_es[marker_pos*3+2:]}")
        print()
        
        # Vérifier si les données sont identiques
        if context_en == context_es:
            print("   ✅ Les données ENGLISH et SPANISH sont IDENTIQUES à cet offset")
            print("   => C'est du padding/bruit, pas du texte valide!")
        else:
            print("   ❌ Les données sont DIFFÉRENTES")
            # Compter les différences
            diffs = sum(1 for a, b in zip(context_en, context_es) if a != b)
            print(f"   {diffs} bytes différents sur {len(context_en)}")
        
        print()
    
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print()


if __name__ == "__main__":
    analyze_failures()
