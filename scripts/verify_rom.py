#!/usr/bin/env python3
"""
Script de vérification rapide pour confirmer que la ROM est prête
"""

import struct
from pathlib import Path

ORIG_ROM = Path("totranslate.gba")
NEW_ROM = Path("totranslate_fr.gba")
SENSITIVE_THRESHOLD = 0x100000

def main():
    print("=" * 70)
    print("VÉRIFICATION ROM TRADUITE")
    print("=" * 70)

    if not ORIG_ROM.exists():
        print("✗ ROM originale introuvable")
        return False

    if not NEW_ROM.exists():
        print("✗ ROM traduite introuvable")
        return False

    orig = ORIG_ROM.read_bytes()
    new = NEW_ROM.read_bytes()

    # 1. Taille
    print(f"\n1. Taille ROM")
    print(f"   Original: {len(orig):,} octets")
    print(f"   Traduit:  {len(new):,} octets")
    if len(orig) != len(new):
        print("   ⚠ Tailles différentes")
    else:
        print("   ✓ Taille identique")

    # 2. Entry Code
    print(f"\n2. Entry Code (0x80000-0x81000)")
    entry_bad_ptrs = 0
    ptr_locs = [0x807E4, 0x80AA8, 0x80AC8, 0x80BC0, 0x80C30]

    for pos in ptr_locs:
        old_val = struct.unpack('<I', orig[pos:pos+4])[0]
        new_val = struct.unpack('<I', new[pos:pos+4])[0]

        if (old_val & 0xFE000000) == 0x08000000:
            new_target = new_val & 0x00FFFFFF
            if new_target < SENSITIVE_THRESHOLD:
                entry_bad_ptrs += 1
                print(f"   ✗ {hex(pos)}: pointe vers {hex(new_target)} (< 1MB)")

    if entry_bad_ptrs == 0:
        print(f"   ✓ Tous les pointeurs sûrs (> 1MB)")

    # 3. Bloc événement
    print(f"\n3. Bloc Événement 0x1F2D9EB")
    ptr_val = 0x08000000 + 0x1F2D9EB
    ptr_bytes = struct.pack('<I', ptr_val)
    ptr_loc = orig.find(ptr_bytes)

    if ptr_loc != -1:
        new_ptr = struct.unpack('<I', new[ptr_loc:ptr_loc+4])[0]
        new_target = new_ptr & 0x00FFFFFF
        print(f"   Relocalisé vers: {hex(new_target)}")

        if new_target > SENSITIVE_THRESHOLD:
            print(f"   ✓ Dans zone sûre (> 1MB)")
        else:
            print(f"   ✗ Dans zone sensible (< 1MB)")
    else:
        print(f"   ✗ Pointeur non trouvé")

    # 4. Résultat
    print("\n" + "=" * 70)

    if entry_bad_ptrs == 0 and new_target > SENSITIVE_THRESHOLD:
        print("✓✓✓ ROM VALIDÉE - PRÊTE POUR TEST")
        print("\nLe jeu devrait:")
        print("  - Démarrer sans écran blanc")
        print("  - Afficher les dialogues traduits")
        print("  - Fonctionner sans boucle sur les événements")
        return True
    else:
        print("✗ PROBLÈMES DÉTECTÉS")
        print("\nLa ROM nécessite des corrections supplémentaires.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
