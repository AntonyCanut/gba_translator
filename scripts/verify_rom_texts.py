#!/usr/bin/env python3
"""
Verify that translated texts are correctly inserted in the ROM.
Check both in-place and relocated texts.
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

def main():
    if not ROM_PATH.exists():
        print(f"Error: {ROM_PATH} not found. Run 'make tests' first.")
        return
    
    rom = ROM_PATH.read_bytes()
    orig_rom = ORIGINAL_ROM.read_bytes()
    value_to_seq = inject_translations.load_charmap(CHARMAP_PATH)
    
    lines = TEXT_FILE.read_text(encoding="utf-8").splitlines()
    
    print(f"Checking ALL texts from {TEXT_FILE}...\n")
    
    mismatches = []
    matches = 0
    relocated = 0
    
    for i, line in enumerate(lines):
        if ": " not in line:
            continue
        
        offset_str, text = line.split(": ", 1)
        offset = int(offset_str, 16)
        
        # Encode the expected text
        try:
            encoded = inject_translations.encode_text(text, value_to_seq)
        except Exception as e:
            print(f"Line {i+1}: Encoding error: {e}")
            continue
        
        # Read from ROM at that offset
        rom_data = rom[offset : offset + len(encoded)]
        
        if rom_data == encoded:
            matches += 1
        else:
            # Check if text was relocated by finding a pointer
            pointer_val = POINTER_BASE + offset
            pointer_bytes = struct.pack("<I", pointer_val)
            ptr_pos = orig_rom.find(pointer_bytes)
            
            if ptr_pos != -1:
                # Read where pointer now points in the new ROM
                new_ptr_val = struct.unpack("<I", rom[ptr_pos:ptr_pos+4])[0]
                new_offset = new_ptr_val - POINTER_BASE
                
                if 0 < new_offset < len(rom):
                    new_rom_data = rom[new_offset : new_offset + len(encoded)]
                    if new_rom_data == encoded:
                        relocated += 1
                        continue
            
            # Try to find the encoded text anywhere
            pos = rom.find(encoded)
            if pos != -1:
                relocated += 1
            else:
                mismatches.append({
                    "line": i + 1,
                    "offset": offset_str,
                    "text_preview": text[:50],
                    "encoded_len": len(encoded),
                    "rom_preview": rom_data[:20].hex() if rom_data else "N/A"
                })
    
    print(f"Results:")
    print(f"  Matches (in-place): {matches}")
    print(f"  Relocated: {relocated}")
    print(f"  Mismatches: {len(mismatches)}")
    
    if mismatches:
        print(f"\nMismatch details:")
        for m in mismatches[:20]:
            print(f"  Line {m['line']} ({m['offset']}): {m['text_preview']}...")
            print(f"    ROM has: {m['rom_preview']}")

if __name__ == "__main__":
    main()
