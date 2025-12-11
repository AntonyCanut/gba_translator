#!/usr/bin/env python3
"""
Deep investigation of a specific offset that shows blank in game.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import inject_translations
import struct

ROM_PATH = Path("totranslate_test.gba")
ORIGINAL_ROM = Path("totranslate.gba")
CHARMAP_PATH = Path("charmap_firered.txt")
POINTER_BASE = 0x08000000

TARGET_OFFSET = 0x1F2D1D7

def main():
    rom = ROM_PATH.read_bytes()
    orig_rom = ORIGINAL_ROM.read_bytes()
    value_to_seq = inject_translations.load_charmap(CHARMAP_PATH)
    
    # Expected text from chunk_76.txt line 170
    expected_text = "Hein ? Qui es-tu ?\\pJe suis presque sûr d'être seul\\nquand ils m'ont jeté ici.\\p…\\p{PLAYER}, hein ?\\pEt tu dis que tu t'es fait aspirer\\nici par un portail magique ?\\pC'est une sacrée entrée."
    
    print(f"=== Investigation of offset {hex(TARGET_OFFSET)} ===\n")
    
    # 1. What was originally at this offset?
    print("1. Original ROM content at this offset:")
    orig_data = orig_rom[TARGET_OFFSET:TARGET_OFFSET + 50]
    print(f"   Hex: {orig_data.hex()}")
    
    # Find the original text end (0xFF terminator)
    orig_end = orig_rom.find(b'\xff', TARGET_OFFSET)
    orig_len = orig_end - TARGET_OFFSET + 1 if orig_end != -1 else 0
    print(f"   Original text length: {orig_len} bytes")
    
    # 2. What's in the new ROM at this offset?
    print("\n2. New ROM content at this offset:")
    new_data = rom[TARGET_OFFSET:TARGET_OFFSET + 50]
    print(f"   Hex: {new_data.hex()}")
    
    # Is it 0xFF (freed space)?
    if new_data[0] == 0xFF:
        print("   PROBLEM: This offset contains 0xFF (freed space)!")
        print("   The text was likely relocated but this is what the game reads.")
    
    # 3. Check if there's a pointer to this offset
    print("\n3. Searching for pointers to this offset:")
    pointer_val = POINTER_BASE + TARGET_OFFSET
    pointer_bytes = struct.pack("<I", pointer_val)
    
    ptr_positions_orig = []
    pos = 0
    while True:
        pos = orig_rom.find(pointer_bytes, pos)
        if pos == -1:
            break
        ptr_positions_orig.append(pos)
        pos += 1
    
    if ptr_positions_orig:
        print(f"   Found {len(ptr_positions_orig)} pointer(s) in ORIGINAL ROM at: {[hex(p) for p in ptr_positions_orig]}")
        
        for ptr_pos in ptr_positions_orig:
            orig_ptr = struct.unpack("<I", orig_rom[ptr_pos:ptr_pos+4])[0]
            new_ptr = struct.unpack("<I", rom[ptr_pos:ptr_pos+4])[0]
            print(f"\n   Pointer at {hex(ptr_pos)}:")
            print(f"     Original value: {hex(orig_ptr)} -> offset {hex(orig_ptr - POINTER_BASE)}")
            print(f"     New value:      {hex(new_ptr)} -> offset {hex(new_ptr - POINTER_BASE)}")
            
            if orig_ptr != new_ptr:
                new_offset = new_ptr - POINTER_BASE
                if 0 < new_offset < len(rom):
                    relocated_data = rom[new_offset:new_offset + 50]
                    print(f"     Relocated text: {relocated_data.hex()}")
    else:
        print("   NO POINTER FOUND to this offset!")
        print("   This text cannot be relocated because the game won't find it.")
    
    # 4. Try to find where the expected text actually is
    print("\n4. Where is the expected text in the new ROM?")
    try:
        encoded = inject_translations.encode_text(expected_text, value_to_seq)
        print(f"   Encoded length: {len(encoded)} bytes")
        pos = rom.find(encoded)
        if pos != -1:
            print(f"   FOUND at offset {hex(pos)}")
        else:
            print("   NOT FOUND in ROM!")
            # Check if it's at the original location
            at_orig = rom[TARGET_OFFSET:TARGET_OFFSET + len(encoded)]
            if at_orig == encoded:
                print("   Actually it IS at the original location!")
    except Exception as e:
        print(f"   Encoding error: {e}")

if __name__ == "__main__":
    main()
