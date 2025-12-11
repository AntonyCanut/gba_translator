#!/usr/bin/env python3
"""
Check if the text at 0x1F2D1D7 was written by the run processing or single entry processing.
By examining what data exists at the NEW destination calculated for this text.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import inject_translations
import struct

NEW_ROM = Path("totranslate_test.gba")
ORIG_ROM = Path("totranslate.gba")
CHARMAP_PATH = Path("charmap_firered.txt")
POINTER_BASE = 0x08000000

# From the analysis
TARGET = 0x1F2D1D7
EXPECTED_DEST = 0x1F2F21D  # Where the trace says the run would put this text
POINTER_LOC = 0x1E902E1  # Where the pointer to TARGET is stored

def main():
    rom = NEW_ROM.read_bytes()
    orig_rom = ORIG_ROM.read_bytes()
    value_to_seq = inject_translations.load_charmap(CHARMAP_PATH)
    
    # Expected text
    expected_text = "Hein ? Qui es-tu ?\\pJe suis presque sûr d'être seul\\nquand ils m'ont jeté ici.\\p…\\p{PLAYER}, hein ?\\pEt tu dis que tu t'es fait aspirer\\nici par un portail magique ?\\pC'est une sacrée entrée."
    encoded = inject_translations.encode_text(expected_text, value_to_seq)
    
    print(f"=== Checking locations for {hex(TARGET)} ===\n")
    print(f"Expected encoded length: {len(encoded)} bytes")
    
    # 1. Check original location
    print(f"\n1. Original location ({hex(TARGET)}):")
    orig_data = rom[TARGET:TARGET + len(encoded)]
    if orig_data == encoded:
        print(f"   ✓ Contains CORRECT translated text!")
    else:
        print(f"   ✗ Does NOT contain expected text")
        print(f"   Has: {orig_data[:30].hex()}...")
    
    # 2. Check expected destination (from run calculation)
    print(f"\n2. Expected destination ({hex(EXPECTED_DEST)}):")
    dest_data = rom[EXPECTED_DEST:EXPECTED_DEST + len(encoded)]
    if dest_data == encoded:
        print(f"   ✓ Contains CORRECT translated text!")
    else:
        print(f"   ✗ Does NOT contain expected text")
        if dest_data[:5] == b'\xff' * 5:
            print(f"   Contains 0xFF (empty/freed space)")
        else:
            print(f"   Has: {dest_data[:30].hex()}...")
    
    # 3. Check where pointer actually points
    ptr_val = struct.unpack("<I", rom[POINTER_LOC:POINTER_LOC+4])[0]
    ptr_target = ptr_val - POINTER_BASE
    print(f"\n3. Pointer at {hex(POINTER_LOC)} points to: {hex(ptr_target)}")
    
    ptr_data = rom[ptr_target:ptr_target + min(50, len(encoded))]
    print(f"   Data there: {ptr_data[:30].hex()}...")
    
    if ptr_data == encoded[:len(ptr_data)]:
        print(f"   ✓ Pointer points to correct text!")
    elif ptr_data[:5] == b'\xff' * 5:
        print(f"   ✗ Pointer points to 0xFF (empty space)!")
    else:
        print(f"   ✗ Pointer points to WRONG data!")
    
    # 4. Find where text actually is
    print(f"\n4. Where is the text actually located?")
    pos = rom.find(encoded)
    if pos != -1:
        print(f"   Found at: {hex(pos)}")
        if pos == TARGET:
            print(f"   This is the ORIGINAL location!")
        elif pos == EXPECTED_DEST:
            print(f"   This is the EXPECTED destination!")
        else:
            print(f"   This is somewhere ELSE!")

if __name__ == "__main__":
    main()
