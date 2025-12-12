#!/usr/bin/env python3
"""
Debug script to understand why some texts are not written correctly
"""

import struct
from pathlib import Path

POINTER_BASE = 0x08000000

def find_pointer_location(rom_data, target_offset):
    pointer_val = POINTER_BASE + target_offset
    pointer_bytes = struct.pack('<I', pointer_val)
    pos = rom_data.find(pointer_bytes)
    return pos if pos != -1 else None

def main():
    orig = Path("totranslate.gba").read_bytes()
    new = Path("totranslate_fr.gba").read_bytes()

    # Check the problematic texts
    problem_offsets = [0x1F2D942, 0x1F2D9EB]

    print("=" * 70)
    print("ANALYSE DES TEXTES CORROMPUS")
    print("=" * 70)

    for offset in problem_offsets:
        print(f"\n{hex(offset)}:")
        print("-" * 70)

        # Find where pointer points
        ptr_loc = find_pointer_location(orig, offset)
        if not ptr_loc:
            print("  Aucun pointeur trouvé")
            continue

        # Get new pointer value
        new_ptr_val = struct.unpack('<I', new[ptr_loc:ptr_loc+4])[0]
        new_target = new_ptr_val & 0x00FFFFFF

        print(f"  Pointeur à {hex(ptr_loc)} pointe vers {hex(new_target)}")

        # Check what's at old location
        old_data = orig[offset:offset+200]
        old_ff = old_data.find(b'\xFF')
        if old_ff != -1:
            old_text = old_data[:old_ff+1]
            print(f"  Texte original à {hex(offset)} ({len(old_text)} octets):")
            print(f"    {old_text[:50].hex()}...")

        # Check what's at new location
        new_data = new[new_target:new_target+200]
        new_ff = new_data.find(b'\xFF')

        if new_ff == -1:
            print(f"  ⚠ PAS DE FF à {hex(new_target)}!")
            print(f"    Données: {new_data[:50].hex()}...")

            # Check if it's all zeros
            if all(b == 0 for b in new_data[:50]):
                print(f"    → Zone de zéros, texte NON ÉCRIT")
            else:
                print(f"    → Données corrompues")
        else:
            new_text = new_data[:new_ff+1]
            print(f"  Texte à {hex(new_target)} ({len(new_text)} octets):")
            print(f"    {new_text[:50].hex()}...")

if __name__ == "__main__":
    main()
