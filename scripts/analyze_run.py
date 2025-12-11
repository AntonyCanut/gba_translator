#!/usr/bin/env python3
"""
Check how the run from 0x1F2CFF4 onwards was handled.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import inject_translations
import struct

ROM_PATH = Path("totranslate_test.gba")
ORIGINAL_ROM = Path("totranslate.gba")
CHARMAP_PATH = Path("charmap_firered.txt")
TEXT_FILE = Path("fr_chunks/chunk_76.txt")
POINTER_BASE = 0x08000000

# Run starts around here (from previous analysis)
RUN_START = 0x1F2CFF4

def main():
    rom = ROM_PATH.read_bytes()
    orig_rom = ORIGINAL_ROM.read_bytes()
    value_to_seq = inject_translations.load_charmap(CHARMAP_PATH)
    
    # Load chunk to get expected texts
    lines = TEXT_FILE.read_text(encoding="utf-8").splitlines()
    texts = {}
    for line in lines:
        if ": " not in line:
            continue
        offset_str, text = line.split(": ", 1)
        offset = int(offset_str, 16)
        texts[offset] = text
    
    print(f"=== Analyzing run starting at {hex(RUN_START)} ===\n")
    
    # Check each text in the run (lines 163-175 approx)
    run_offsets = [0x1F2CFF4, 0x1F2D02E, 0x1F2D04E, 0x1F2D07E, 0x1F2D124, 
                   0x1F2D162, 0x1F2D192, 0x1F2D1D7, 0x1F2D28B, 0x1F2D2F9, 0x1F2D3B2]
    
    for offset in run_offsets:
        print(f"\n--- Offset {hex(offset)} ---")
        
        # Find pointer in original ROM
        pointer_val = POINTER_BASE + offset
        pointer_bytes = struct.pack("<I", pointer_val)
        ptr_pos = orig_rom.find(pointer_bytes)
        
        if ptr_pos != -1:
            orig_ptr = struct.unpack("<I", orig_rom[ptr_pos:ptr_pos+4])[0]
            new_ptr = struct.unpack("<I", rom[ptr_pos:ptr_pos+4])[0]
            new_offset = new_ptr - POINTER_BASE
            
            print(f"Pointer at {hex(ptr_pos)}: {hex(orig_ptr)} -> {hex(new_ptr)}")
            
            # Check what's at the new location
            new_data = rom[new_offset:new_offset + 20]
            print(f"New location ({hex(new_offset)}) contains: {new_data.hex()}")
            
            if new_data[0] == 0xFF:
                print("  ⚠️ PROBLEM: New location is 0xFF (freed space)!")
            
            # Check what's at the original location
            orig_loc_data = rom[offset:offset + 20]
            print(f"Original location ({hex(offset)}) contains: {orig_loc_data.hex()}")
        else:
            print("No pointer found for this offset")
        
        # Check if expected text is in ROM
        if offset in texts:
            try:
                encoded = inject_translations.encode_text(texts[offset], value_to_seq)
                pos = rom.find(encoded)
                if pos != -1:
                    print(f"Expected text found at: {hex(pos)}")
                else:
                    print("Expected text NOT FOUND!")
            except Exception as e:
                print(f"Encoding error: {e}")

if __name__ == "__main__":
    main()
