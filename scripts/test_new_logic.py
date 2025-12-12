#!/usr/bin/env python3
"""
Tester la nouvelle logique de construction des runs
"""

from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).parent))
import inject_translations

ORIG_ROM = Path("totranslate.gba")
CHARMAP_PATH = Path("charmap_firered.txt")
COMBINED_FR = Path("fr_chunks/chunk_76.txt")

# Le bloc problématique
PROBLEM_BLOCK = [
    0x1F2D942,
    0x1F2D9B9,
    0x1F2D9EB,
    0x1F2DA1D,
    0x1F2DAAB,
]

POINTER_BASE = 0x08000000

def find_pointers_to(rom_data, target_offset):
    """Trouve tous les pointeurs vers un offset"""
    pointer_val = POINTER_BASE + target_offset
    positions = []

    pointer_bytes = struct.pack("<I", pointer_val)
    pos = 0
    while True:
        pos = rom_data.find(pointer_bytes, pos)
        if pos == -1:
            break
        positions.append((pos, False))
        pos += 1

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
    print("TEST DE LA NOUVELLE LOGIQUE")
    print("=" * 70)

    rom = ORIG_ROM.read_bytes()
    value_to_seq = inject_translations.load_charmap(CHARMAP_PATH)

    # Simuler ordered_offsets
    ordered_offsets = sorted(PROBLEM_BLOCK)

    # Simuler original_lengths
    original_lengths = {}
    for off in ordered_offsets:
        end = rom.find(b'\xFF', off)
        if end != -1:
            original_lengths[off] = end - off + 1

    # Simuler entries_by_offset
    entries_by_offset = {}
    for line in COMBINED_FR.read_text(encoding="utf-8").splitlines():
        if ": " not in line:
            continue
        parts = line.split(": ", 1)
        if len(parts) != 2:
            continue
        off_str = parts[0].split("→")[-1].strip()
        try:
            offset = int(off_str, 16)
            if offset in PROBLEM_BLOCK:
                text = parts[1]
                encoded = inject_translations.encode_text(text, value_to_seq)
                entries_by_offset[offset] = {
                    "text": text[:50],
                    "enc_len": len(encoded),
                    "orig_len": original_lengths[offset]
                }
        except:
            continue

    def has_pointer_for(off):
        return len(find_pointers_to(rom, off)) > 0

    # NOUVELLE LOGIQUE
    print("\n1. CONSTRUCTION DES RUNS (NOUVELLE LOGIQUE)")
    print("-" * 70)

    anchor_for = {}
    run_members = {}
    prev_offset = None
    current_anchor = None

    for off in ordered_offsets:
        is_contiguous = (prev_offset is not None and
                        off == prev_offset + original_lengths[prev_offset])

        if not is_contiguous:
            current_anchor = None
            print(f"\n   {hex(off)}: Nouvelle séquence (pas contigu)")
        else:
            print(f"\n   {hex(off)}: Contigu avec {hex(prev_offset)}")

        has_ptr = has_pointer_for(off)
        print(f"      A un pointeur: {has_ptr}")

        if current_anchor is None and has_ptr:
            current_anchor = off
            print(f"      → Devient ANCHOR (premier du run)")
        elif has_ptr:
            print(f"      → A un pointeur mais garde l'anchor {hex(current_anchor)}")

        if current_anchor is not None:
            anchor_for[off] = current_anchor
            run_members.setdefault(current_anchor, []).append(off)
            print(f"      Ajouté au run de l'anchor {hex(current_anchor)}")

        prev_offset = off

    print("\n2. RÉSULTAT DES RUNS")
    print("-" * 70)

    for anchor, members in sorted(run_members.items()):
        print(f"\n   Anchor {hex(anchor)}:")
        print(f"   Membres: {[hex(m) for m in members]}")
        print(f"   Taille du run: {len(members)}")

        # Calculer tailles
        total_orig = sum(entries_by_offset[m]["orig_len"] for m in members)
        total_new = sum(entries_by_offset[m]["enc_len"] for m in members)

        print(f"   Total original: {total_orig} octets")
        print(f"   Total nouveau:  {total_new} octets")
        print(f"   Delta: {total_new - total_orig:+d} octets")

        if total_new > total_orig:
            print(f"   ✓ Sera relogé (total dépasse)")

    print("\n3. CONCLUSION")
    print("-" * 70)
    print(f"   Nombre de runs créés: {len(run_members)}")
    if len(run_members) == 1:
        print(f"   ✓ SUCCÈS: Le bloc contigu est détecté comme UN SEUL run!")
    else:
        print(f"   ✗ ÉCHEC: Le bloc est encore fragmenté")

if __name__ == "__main__":
    main()
