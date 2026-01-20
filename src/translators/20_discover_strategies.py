#!/usr/bin/env python3
"""
20 - DÉCOUVERTE: Substitutions directes vs Relocalisations réelles

Analyse détaillée pour comprendre le mécanisme exact.
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def extract_and_analyze():
    """Extrait et analyse les données réelles."""
    
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
    print("🎯 DÉCOUVERTE: Stratégies de la ROM espagnole")
    print("=" * 80)
    print()
    
    substitutions = []
    relocations = []
    
    for i, failure in enumerate(failures, 1):
        offset = int(failure['offset'], 16)
        en_text = failure['english_text']
        es_text = failure['spanish_text']
        
        # Trouver la longueur réelle
        en_term = None
        es_term = None
        
        for j in range(offset, min(offset + 100, len(english_rom.rom_data))):
            if en_term is None and english_rom.rom_data[j] == 0x00:
                en_term = j - offset
            if es_term is None and spanish_rom.rom_data[j] == 0x00:
                es_term = j - offset
        
        if en_term == es_term and en_term is not None:
            # Substitution directe
            substitutions.append({
                'offset': offset,
                'length': en_term,
                'en_text': en_text,
                'es_text': es_text,
                'en_bytes': english_rom.rom_data[offset:offset+en_term],
                'es_bytes': spanish_rom.rom_data[offset:offset+es_term],
            })
        else:
            # Relocalisation probable
            relocations.append({
                'offset': offset,
                'en_length': en_term,
                'es_length': es_term,
                'en_text': en_text,
                'es_text': es_text,
            })
    
    print(f"📊 Résultats:")
    print(f"   - Substitutions directes (même longueur): {len(substitutions)}")
    print(f"   - Relocalisations (longueurs différentes): {len(relocations)}")
    print()
    
    if substitutions:
        print("=" * 80)
        print("SUBSTITUTIONS DIRECTES (in-place replacement)")
        print("=" * 80)
        print()
        
        for sub in substitutions:
            print(f"Offset 0x{sub['offset']:08X} (longueur: {sub['length']} bytes)")
            print(f"  EN text: \"{sub['en_text'][:50]}...\"" if len(sub['en_text']) > 50 else f"  EN text: \"{sub['en_text']}\"")
            print(f"  ES text: \"{sub['es_text'][:50]}...\"" if len(sub['es_text']) > 50 else f"  ES text: \"{sub['es_text']}\"")
            
            # Analyser les bytes
            en_hex = ' '.join(f'{b:02x}' for b in sub['en_bytes'][:20])
            es_hex = ' '.join(f'{b:02x}' for b in sub['es_bytes'][:20])
            print(f"  EN bytes: {en_hex}...")
            print(f"  ES bytes: {es_hex}...")
            
            # Chercher un pattern d'encodage
            # Vérifier si c'est un encodage différent (XOR, shift, etc.)
            xor_values = [a ^ b for a, b in zip(sub['en_bytes'], sub['es_bytes'])]
            if len(set(xor_values)) == 1:
                print(f"  ⚡ PATTERN: XOR constant avec 0x{xor_values[0]:02X}!")
            
            print()
    
    if relocations:
        print("=" * 80)
        print("RELOCALISATIONS (textes déplacés ailleurs)")
        print("=" * 80)
        print()
        
        for rel in relocations:
            print(f"Offset 0x{rel['offset']:08X}")
            print(f"  EN length: {rel['en_length']} bytes → ES length: {rel['es_length']} bytes")
            print(f"  EN text: \"{rel['en_text'][:40]}...\"" if len(rel['en_text']) > 40 else f"  EN text: \"{rel['en_text']}\"")
            print(f"  ES text: \"{rel['es_text'][:40]}...\"" if len(rel['es_text']) > 40 else f"  ES text: \"{rel['es_text']}\"")
            print(f"  💡 Les données sont probablement DANS LA ROM mais à un offset DIFFÉRENT")
            print()


if __name__ == "__main__":
    extract_and_analyze()
