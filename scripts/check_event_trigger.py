#!/usr/bin/env python3
"""
Script de vérification finale pour l'événement à 0x1F2D9EB
"""

from pathlib import Path
import struct

ORIG_ROM = Path("totranslate.gba")
NEW_ROM = Path("totranslate_fr.gba")
POINTER_BASE = 0x08000000

# Le bloc problématique complet
PROBLEM_BLOCK = [
    0x1F2D942,
    0x1F2D9B9,
    0x1F2D9EB,  # L'événement qui posait problème
    0x1F2DA1D,
    0x1F2DAAB,
]

def find_pointers_to(rom_data, target_offset):
    """Trouve tous les pointeurs vers un offset"""
    pointer_val = POINTER_BASE + target_offset
    positions = []

    # Normal pointers
    pointer_bytes = struct.pack("<I", pointer_val)
    pos = 0
    while True:
        pos = rom_data.find(pointer_bytes, pos)
        if pos == -1:
            break
        positions.append(pos)
        pos += 1

    # Thumb pointers
    pointer_val_thumb = pointer_val | 1
    pointer_bytes_thumb = struct.pack("<I", pointer_val_thumb)
    pos = 0
    while True:
        pos = rom_data.find(pointer_bytes_thumb, pos)
        if pos == -1:
            break
        positions.append(pos)
        pos += 1

    return positions

def get_relocation_target(rom_data, orig_offset):
    """Trouve où un offset a été relocalisé"""
    pointers = find_pointers_to(open(ORIG_ROM, 'rb').read(), orig_offset)
    if not pointers:
        return None

    # Lire le premier pointeur dans la nouvelle ROM
    new_ptr = struct.unpack("<I", rom_data[pointers[0]:pointers[0]+4])[0]
    return new_ptr & 0x00FFFFFF

def main():
    print("=" * 70)
    print("VÉRIFICATION FINALE DE L'ÉVÉNEMENT 0x1F2D9EB")
    print("=" * 70)

    orig = ORIG_ROM.read_bytes()
    new = NEW_ROM.read_bytes()

    print("\n1. ÉTAT DES RELOCALISATIONS")
    print("-" * 70)

    relocations = {}
    for offset in PROBLEM_BLOCK:
        target = get_relocation_target(new, offset)
        relocations[offset] = target

        status = "RELOCALISÉ" if target and target != offset else "EN PLACE"
        print(f"   {hex(offset)}: {status}", end="")
        if target and target != offset:
            print(f" → {hex(target)}")
        else:
            print()

    print("\n2. VÉRIFICATION DE LA CONTIGUÏTÉ")
    print("-" * 70)

    all_contiguous = True
    prev_offset = None
    prev_target = None

    for offset in PROBLEM_BLOCK:
        target = relocations[offset]
        if not target:
            continue

        # Trouver la longueur du texte
        ff_pos = new.find(b'\xFF', target)
        if ff_pos == -1:
            print(f"   ⚠ ERREUR: Pas de FF trouvé à {hex(target)}")
            all_contiguous = False
            continue

        text_len = ff_pos - target + 1

        if prev_target is not None:
            expected_next = prev_target + prev_len
            gap = target - expected_next

            print(f"   {hex(prev_offset)} + {prev_len} = {hex(expected_next)}")
            print(f"   Prochain: {hex(target)}")

            if gap == 0:
                print(f"   ✓ CONTIGU")
            else:
                print(f"   ✗ GAP de {gap} octets")
                all_contiguous = False

        prev_offset = offset
        prev_target = target
        prev_len = text_len

    print("\n3. VALIDATION DES DONNÉES")
    print("-" * 70)

    all_valid = True
    for offset in PROBLEM_BLOCK:
        target = relocations[offset]
        if not target:
            continue

        # Vérifier que les données sont valides (pas que des 0x00)
        data = new[target:target+50]

        if all(b == 0 for b in data):
            print(f"   ✗ {hex(offset)} → {hex(target)}: Données vides (0x00)")
            all_valid = False
        elif b'\xFF' not in data:
            print(f"   ⚠ {hex(offset)} → {hex(target)}: Pas de terminateur FF")
            all_valid = False
        else:
            ff_pos = data.find(b'\xFF')
            print(f"   ✓ {hex(offset)} → {hex(target)}: {ff_pos+1} octets valides")

    print("\n4. RÉSULTAT FINAL")
    print("-" * 70)

    if all_contiguous and all_valid:
        print("   ✓✓✓ SUCCÈS COMPLET !")
        print("   Le bloc est relocalisé de façon contiguë avec des données valides.")
        print("   L'événement à 0x1F2D9EB devrait maintenant fonctionner correctement.")
    else:
        if not all_contiguous:
            print("   ✗ Le bloc n'est pas contigu")
        if not all_valid:
            print("   ✗ Certaines données sont invalides")
        print("   → Le problème persiste")

    print("\n5. INSTRUCTIONS DE TEST")
    print("-" * 70)
    print("   1. Chargez totranslate_fr.gba dans votre émulateur")
    print("   2. Naviguez jusqu'à l'événement qui se trouvait à 0x1F2D9EB")
    print("   3. Vérifiez que le dialogue s'affiche correctement")
    print("   4. Vérifiez que l'événement suivant se déclenche (pas de boucle)")
    print()

if __name__ == "__main__":
    main()
