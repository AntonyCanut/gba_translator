#!/usr/bin/env python3
"""
18 - Découvrir le mécanisme de relocalisation

Cherche les patterns de relocalisation dans la ROM espagnole.
- Tables d'indirection
- Pointeurs
- Marqueurs spéciaux
- Zone de code supplémentaire
"""

import sys
import json
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def find_relocation_pattern():
    """Cherche les patterns de relocalisation."""
    
    report_path = Path('output/tests/2026-01-14_spanish_simulation_report.json')
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    failures = report['failures']
    
    # Charger les ROMs
    english_rom = ROMReader('input/roms/englishrom.gba')
    spanish_rom = ROMReader('input/roms/spanishrom.gba')
    english_rom.load()
    spanish_rom.load()
    
    print()
    print("=" * 80)
    print("🔍 RECHERCHE: Mécanisme de relocalisation")
    print("=" * 80)
    print()
    
    # Collecter tous les offsets d'échec
    failure_offsets = [int(f['offset'], 16) for f in failures]
    
    print(f"📍 Offsets à analyser: {len(failure_offsets)}")
    for i, offset in enumerate(failure_offsets, 1):
        print(f"   {i:2d}. 0x{offset:08X}")
    
    print()
    print("=" * 80)
    print("HYPOTHÈSE 1: Marque spéciale vs encodage différent")
    print("=" * 80)
    print()
    
    for offset in failure_offsets:
        # Récupérer le byte à l'offset dans les deux ROMs
        en_byte = english_rom.rom_data[offset]
        es_byte = spanish_rom.rom_data[offset]
        
        print(f"0x{offset:08X}: EN=0x{en_byte:02X} ({chr(en_byte) if 32 <= en_byte <= 126 else '?'}), "
              f"ES=0x{es_byte:02X} ({chr(es_byte) if 32 <= es_byte <= 126 else '?'})")
        
        # Chercher un pattern récurrent
        if es_byte in [0xFF, 0xFE, 0x00, 0x01, 0x02]:
            print(f"      → Marqueur spécial détecté: 0x{es_byte:02X}")
    
    print()
    print("=" * 80)
    print("HYPOTHÈSE 2: Indirection via pointeur")
    print("=" * 80)
    print()
    
    for offset in failure_offsets:
        # Avant chaque offset échoué, chercher un pointeur GBA valide
        for back_offset in [4, 8, 12, 16, 20]:
            ptr_offset = offset - back_offset
            if ptr_offset >= 0:
                # Lire comme pointeur little-endian
                ptr_bytes = english_rom.rom_data[ptr_offset:ptr_offset+4]
                ptr_value = struct.unpack('<I', ptr_bytes)[0]
                
                # Vérifier si c'est un pointeur GBA valide (commence par 0x08)
                if (ptr_value & 0xFF000000) == 0x08000000:
                    rom_offset = ptr_value - 0x08000000
                    es_ptr_value = struct.unpack('<I', spanish_rom.rom_data[ptr_offset:ptr_offset+4])[0]
                    
                    if ptr_value != es_ptr_value:
                        print(f"0x{offset:08X} - Pointeur à -0x{back_offset:02X}:")
                        print(f"   EN: 0x{ptr_value:08X} → 0x{rom_offset:08X}")
                        print(f"   ES: 0x{es_ptr_value:08X}")
                        print(f"   → DIFFÉRENT! Peut indiquer une relocalisation")
                        print()
                        break
    
    print()
    print("=" * 80)
    print("HYPOTHÈSE 3: Encodage alternatif (compression, table lookup)")
    print("=" * 80)
    print()
    
    for i, offset in enumerate(failure_offsets[:3]):  # Premiers 3 cas
        print(f"\nCas {i+1}: 0x{offset:08X}")
        
        # Extraire 30 bytes avant et 50 après l'offset
        start = max(0, offset - 30)
        end = min(len(english_rom.rom_data), offset + 50)
        
        en_data = english_rom.rom_data[start:end]
        es_data = spanish_rom.rom_data[start:end]
        
        marker = offset - start
        
        print(f"EN: {' '.join(f'{b:02x}' for b in en_data[:marker])} [{en_data[marker]:02x}] {' '.join(f'{b:02x}' for b in en_data[marker+1:])}")
        print(f"ES: {' '.join(f'{b:02x}' for b in es_data[:marker])} [{es_data[marker]:02x}] {' '.join(f'{b:02x}' for b in es_data[marker+1:])}")
        
        # Chercher des patterns
        # Terminator bytes
        if en_data[marker] == 0x00 and es_data[marker] != 0x00:
            print(f"→ Terminateur MANQUANT dans ES à cet offset")
        
        if en_data[marker] == 0xFF and es_data[marker] != 0xFF:
            print(f"→ Padding terminateur MODIFIÉ")
        
        # Vérifier si ES continue après où EN s'arrête
        en_term_pos = None
        for j in range(marker, min(marker+30, len(en_data))):
            if en_data[j] == 0x00:
                en_term_pos = j
                break
        
        if en_term_pos:
            print(f"→ EN se termine à +{en_term_pos - marker} bytes")
            print(f"→ ES à cette position: 0x{es_data[en_term_pos]:02x}")
    
    print()
    print("=" * 80)
    print("HYPOTHÈSE 4: Les données sont-elles dans la ROM espagnole?")
    print("=" * 80)
    print()
    
    # Charger les textes extraits
    with open('output/extracted_texts/spanishrom_texts.json', 'r', encoding='utf-8') as f:
        spanish_texts = json.load(f)
    
    # Pour chaque cas échoué, chercher le texte espagnol dans d'autres offsets
    found_relocations = 0
    
    for failure in failures[:3]:  # Premiers 3 cas
        offset = int(failure['offset'], 16)
        english_text = failure['english_text']
        spanish_text = failure['spanish_text']
        
        print(f"\nOffsets {hex(offset)}:")
        print(f"  EN: \"{english_text}\"")
        print(f"  ES: \"{spanish_text}\"")
        
        # Chercher si ce texte espagnol existe ailleurs dans la ROM
        # (ceci est une approximation)
        # On vérifierait normalement en cherchant dans la structure
        print(f"  → À investiguer: où ce texte est-il implanté dans ES?")


if __name__ == "__main__":
    find_relocation_pattern()
