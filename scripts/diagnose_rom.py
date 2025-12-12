#!/usr/bin/env python3
"""
Diagnostiquer pourquoi la ROM ne se lance pas
"""

from pathlib import Path
import struct

ORIG_ROM = Path("totranslate.gba")
NEW_ROM = Path("totranslate_fr.gba")
POINTER_BASE = 0x08000000

# Zones critiques pour le démarrage du jeu
CRITICAL_AREAS = [
    (0x000000, 0x0001000, "ROM Header"),
    (0x080000, 0x081000, "Code Entry Point"),
]

def check_pointers_validity(rom_data):
    """Vérifier que tous les pointeurs pointent vers des zones valides"""
    errors = []

    # Scanner les pointeurs suspects
    for i in range(0, min(len(rom_data), 0x200000), 4):
        val = struct.unpack("<I", rom_data[i:i+4])[0]

        # Est-ce un pointeur potentiel?
        if (val & 0xFF000000) == 0x08000000 or (val & 0xFF000000) == 0x09000000:
            target = val & 0x00FFFFFF

            # Le pointeur pointe-t-il en dehors de la ROM?
            if target >= len(rom_data):
                errors.append(f"Pointeur invalide à {hex(i)}: pointe vers {hex(val)} (hors ROM)")
                if len(errors) >= 10:
                    break

    return errors

def compare_critical_areas(orig, new):
    """Comparer les zones critiques entre l'original et le nouveau"""
    issues = []

    for start, end, name in CRITICAL_AREAS:
        orig_data = orig[start:end]
        new_data = new[start:end]

        if orig_data != new_data:
            # Compter les différences
            diff_count = sum(1 for i in range(len(orig_data)) if orig_data[i] != new_data[i])
            issues.append(f"{name}: {diff_count} octets modifiés sur {end-start}")

    return issues

def main():
    print("=" * 70)
    print("DIAGNOSTIC DE LA ROM")
    print("=" * 70)

    orig = ORIG_ROM.read_bytes()
    new = NEW_ROM.read_bytes()

    print(f"\nTaille ROM originale: {len(orig):,} octets")
    print(f"Taille nouvelle ROM:  {len(new):,} octets")

    if len(new) > len(orig):
        print(f"⚠ ROM étendue de {len(new) - len(orig):,} octets")

    print("\n1. ZONES CRITIQUES")
    print("-" * 70)

    issues = compare_critical_areas(orig, new)
    if issues:
        for issue in issues:
            print(f"  ⚠ {issue}")
    else:
        print("  ✓ Zones critiques inchangées")

    print("\n2. POINTEURS INVALIDES")
    print("-" * 70)

    errors = check_pointers_validity(new)
    if errors:
        print(f"  ⚠ Trouvé {len(errors)} pointeurs invalides:")
        for error in errors[:5]:
            print(f"    - {error}")
    else:
        print("  ✓ Pas de pointeurs invalides détectés")

    print("\n3. INTÉGRITÉ GLOBALE")
    print("-" * 70)

    # Vérifier les zones remplies de 0x00 (signe de corruption)
    zero_runs = []
    i = 0
    while i < len(new):
        if new[i] == 0x00:
            start = i
            while i < len(new) and new[i] == 0x00:
                i += 1
            length = i - start
            if length > 1000:  # Plus de 1KB de zéros
                zero_runs.append((start, length))
        else:
            i += 1

    if zero_runs:
        print(f"  ⚠ Zones suspectes de zéros:")
        for start, length in zero_runs[:5]:
            print(f"    - {hex(start)}: {length:,} octets de 0x00")
    else:
        print("  ✓ Pas de zones suspectes de zéros")

if __name__ == "__main__":
    main()
