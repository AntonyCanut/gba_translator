#!/usr/bin/env python3
"""
Analyser comment le script actuel traite les blocs contigus
"""

from pathlib import Path
import struct

# Simuler la logique actuelle de inject_translations.py

ORIG_ROM = Path("totranslate.gba")
CHARMAP_PATH = Path("charmap_firered.txt")
COMBINED_FR = Path("combined_fr.txt")
POINTER_BASE = 0x08000000

# Le bloc problématique
PROBLEM_BLOCK = [
    0x1F2D942,
    0x1F2D9B9,
    0x1F2D9EB,
    0x1F2DA1D,
    0x1F2DAAB,
]

def find_pointers_to(rom_data, target_offset):
    """Trouve tous les pointeurs vers un offset"""
    pointer_val = POINTER_BASE + target_offset
    positions = []

    # Normal
    pointer_bytes = struct.pack("<I", pointer_val)
    pos = 0
    while True:
        pos = rom_data.find(pointer_bytes, pos)
        if pos == -1:
            break
        positions.append((pos, False))
        pos += 1

    # Thumb
    pointer_val_thumb = pointer_val | 1
    pointer_bytes_thumb = struct.pack("<I", pointer_val_thumb)
    pos = 0
    while True:
        pos = rom_data.find(pointer_bytes_thumb, pos)
        if pos == -1:
            break
        positions.append((pos, True))
        pos += 1

    return positions

def main():
    print("=" * 70)
    print("ANALYSE DU COMPORTEMENT ACTUEL DU SCRIPT")
    print("=" * 70)

    rom = ORIG_ROM.read_bytes()

    # Simuler ordered_offsets
    ordered_offsets = sorted(PROBLEM_BLOCK)

    # Simuler original_lengths
    original_lengths = {}
    for off in ordered_offsets:
        end = rom.find(b'\xFF', off)
        if end != -1:
            original_lengths[off] = end - off + 1

    print("\n1. DÉTECTION DE LA CONTIGUÏTÉ")
    print("-" * 70)

    prev_offset = None
    for off in ordered_offsets:
        if prev_offset is not None:
            expected_next = prev_offset + original_lengths[prev_offset]
            is_contiguous = (off == expected_next)
            gap = off - expected_next if not is_contiguous else 0

            print(f"   {hex(prev_offset)} + {original_lengths[prev_offset]} = {hex(expected_next)}")
            print(f"   Prochain offset: {hex(off)}")
            print(f"   → {'CONTIGU' if is_contiguous else f'GAP de {gap} octets'}")
            print()
        prev_offset = off

    # Simuler la construction des runs avec la logique ACTUELLE
    print("\n2. CONSTRUCTION DES RUNS (LOGIQUE ACTUELLE)")
    print("-" * 70)

    anchor_for = {}
    run_members = {}
    prev_offset = None
    current_anchor = None

    def has_pointer_for(off):
        return len(find_pointers_to(rom, off)) > 0

    for off in ordered_offsets:
        # Logique actuelle
        if prev_offset is None or off != prev_offset + original_lengths[prev_offset]:
            current_anchor = None
            print(f"\n   {hex(off)}: Nouvelle séquence (pas contigu)")
        else:
            print(f"\n   {hex(off)}: Contigu avec {hex(prev_offset)}")

        has_ptr = has_pointer_for(off)
        print(f"      A un pointeur: {has_ptr}")

        if has_ptr:
            current_anchor = off
            print(f"      → Devient ANCHOR (écrase l'anchor précédent!)")

        if current_anchor is not None:
            anchor_for[off] = current_anchor
            run_members.setdefault(current_anchor, []).append(off)
            print(f"      Ajouté au run de l'anchor {hex(current_anchor)}")
        else:
            print(f"      PAS D'ANCHOR - ignoré")

        prev_offset = off

    print("\n3. RÉSULTAT DES RUNS")
    print("-" * 70)

    for anchor, members in sorted(run_members.items()):
        print(f"\n   Anchor {hex(anchor)}:")
        print(f"   Membres: {[hex(m) for m in members]}")
        print(f"   Taille du run: {len(members)}")

    # Conclusion
    print("\n4. CONCLUSION")
    print("-" * 70)
    print(f"   Nombre de runs créés: {len(run_members)}")
    print(f"   PROBLÈME: Chaque texte avec pointeur devient un nouveau run!")
    print(f"   → Le bloc contigu est fragmenté en {len(run_members)} runs séparés")
    print(f"   → Quand un texte est trop long, il écrase les suivants")

if __name__ == "__main__":
    main()
