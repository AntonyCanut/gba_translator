#!/usr/bin/env python3
"""
22 - Localiser la table de lookup

Les bytes 0x66, 0xBB, 0x33, 0xAA, 0x70, 0x88, 0x77, 0x11, 0x17, 0x71, 0xEE
sont probablement des INDICES dans une table de lookup.

Cherchons:
1. Où cette table est stockée
2. Comment elle est utilisée
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.rom_reader import ROMReader


def find_lookup_table():
    """Cherche la table de lookup."""
    
    print()
    print("=" * 80)
    print("🔍 RECHERCHE: Table de lookup")
    print("=" * 80)
    print()
    
    english_rom = ROMReader('input/roms/englishrom.gba')
    spanish_rom = ROMReader('input/roms/spanishrom.gba')
    english_rom.load()
    spanish_rom.load()
    
    # Les indices observés
    common_bytes = [0x66, 0xBB, 0x33, 0xAA, 0x70, 0x88, 0x77, 0x11, 0x17, 0x71, 0xEE]
    
    print(f"📍 Bytes indices observés: {[f'0x{b:02X}' for b in common_bytes]}")
    print()
    
    # Chercher une zone de pattern répétitif
    # Les tables de lookup sont souvent à des adresses alignées (multiples de 4, 16, etc.)
    
    print("Cherchant les zones où ces bytes se répliquent...\n")
    
    # Compter les occurrences de chaque byte dans les deux ROMs
    for byte_val in common_bytes:
        en_count = english_rom.rom_data.count(bytes([byte_val]))
        es_count = spanish_rom.rom_data.count(bytes([byte_val]))
        
        print(f"Byte 0x{byte_val:02X}: EN={en_count} fois, ES={es_count} fois", end="")
        
        if en_count != es_count:
            print(f" ⚠️ Différence: {es_count - en_count}")
        else:
            print(" ✅ Identical count")
    
    print()
    print("=" * 80)
    print("HYPOTHÈSE ALTERNATIVE: Données corrompues/mal décodées")
    print("=" * 80)
    print()
    
    print("""
La forte proportion de bytes identiques (0x66, 0xBB, 0x33, 0xAA) suggère que
ces zones ne contiennent PAS des TEXTES VALIDES.

Les "substitutions directes" que nous voyons pourraient être:
1. Des zones de PADDING/DONNÉES CORROMPUES dans la ROM anglaise
2. Remplacées par du VRAI TEXTE dans la ROM espagnole

Ou inversement:
1. La ROM anglaise contient du BRUIT/PADDING
2. La ROM espagnole l'a nettoyé ou réimplanté différemment

Les 11 cas d'échec pourraient donc être des ZONES NON-TEXTUELLES
que notre système détecte correctement comme problématiques!
""")


if __name__ == "__main__":
    find_lookup_table()
