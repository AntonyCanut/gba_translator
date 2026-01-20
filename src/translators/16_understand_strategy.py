#!/usr/bin/env python3
"""
16 - Comprendre la stratégie de la ROM espagnole

Analyse comment la ROM espagnole gère les débordements.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader
from src.core.padding_detector import PaddingDetector


def analyze_strategy():
    """Analyse la stratégie utilisée par la ROM espagnole."""
    
    # Charger le rapport de tests
    report_path = Path('output/tests/2026-01-14_spanish_simulation_report.json')
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    failures = report['failures']
    
    # Charger les ROMs
    print("📖 Chargement des ROMs et diff_with_padding...")
    english_rom = ROMReader('input/roms/englishrom.gba')
    spanish_rom = ROMReader('input/roms/spanishrom.gba')
    english_rom.load()
    spanish_rom.load()
    
    # Charger diff_with_padding
    with open('output/differences/2026-01-13_diff_with_padding.json', 'r', encoding='utf-8') as f:
        diff_data = json.load(f)
    
    # Créer un dictionnaire des textes par offset
    texts_by_offset = {t['offset']: t for t in diff_data['texts']}
    
    print()
    print("=" * 80)
    print("STRATÉGIE DE LA ROM ESPAGNOLE - ANALYSE DES 11 CAS")
    print("=" * 80)
    print()
    
    for i, failure in enumerate(failures, 1):
        offset = failure['offset']
        offset_int = int(offset, 16)
        
        print(f"\n{i}. Offset {offset}")
        print(f"   Type: {failure['category']} | Débordement: {failure['overflow']} bytes")
        
        # Trouver le texte de référence
        if offset_int in texts_by_offset:
            text_info = texts_by_offset[offset_int]
            print(f"   Padding info trouvé:")
            print(f"   - Text: '{text_info['text'][:40]}...'")
            print(f"   - Encoding: {text_info['encoding']}")
            print(f"   - Padding: {text_info['padding_available']} bytes")
            print(f"   - Real max: {text_info['real_max_length']} bytes")
        
        # Analyser les bytes avant/après l'offset
        print(f"\n   Stratégie détectée:")
        
        # Extraire contexte (30 bytes avant et après)
        start = max(0, offset_int - 30)
        end = min(len(english_rom.rom_data), offset_int + 150)
        
        en_context = english_rom.rom_data[start:end]
        es_context = spanish_rom.rom_data[start:end]
        
        # Chercher un pattern de réallocation (pointeurs changés)
        has_pointer_changes = False
        has_relocation = False
        
        # Vérifier si il y a des 00 FF patterns (padding/séparation)
        en_padding_count = sum(1 for j in range(start, min(end, offset_int + 50)) if english_rom.rom_data[j] == 0xFF)
        es_padding_count = sum(1 for j in range(start, min(end, offset_int + 50)) if spanish_rom.rom_data[j] == 0xFF)
        
        if en_padding_count != es_padding_count:
            print(f"   → Padding/séparation modifié")
            print(f"      EN: {en_padding_count} bytes 0xFF vs ES: {es_padding_count} bytes 0xFF")
        
        # Compter les bytes identiques autour de l'offset
        identical_before = sum(1 for j in range(max(start, offset_int-20), offset_int) 
                              if english_rom.rom_data[j] == spanish_rom.rom_data[j])
        
        identical_after = sum(1 for j in range(offset_int, min(end, offset_int+20)) 
                             if english_rom.rom_data[j] == spanish_rom.rom_data[j])
        
        print(f"   → Similarité:")
        print(f"      Avant offset: {identical_before}/20 bytes identiques")
        print(f"      Après offset: {identical_after}/20 bytes identiques")
        
        if identical_before == 20 and identical_after < 15:
            print(f"   → Cet offset marque un CHANGEMENT STRUCTUREL")
            print(f"      Le texte a probablement été RELOCALISÉ dans la ROM!")
        
        print()


if __name__ == "__main__":
    analyze_strategy()
