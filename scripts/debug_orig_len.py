#!/usr/bin/env python3
"""
Debug: Check what orig_len actually is for 0x1F2D192 
and if range(offset + 1, offset + orig_len) includes 0x1F2D1D7
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import inject_translations

ROM_PATH = Path("totranslate.gba")
CHARMAP_PATH = Path("charmap_firered.txt")
TEXT_FILE = Path("fr_chunks/chunk_76.txt")

OFFSET = 0x1F2D192
TARGET = 0x1F2D1D7

def main():
    rom = ROM_PATH.read_bytes()
    value_to_seq = inject_translations.load_charmap(CHARMAP_PATH)
    
    # Find orig_len for OFFSET
    end = rom.find(b"\xff", OFFSET)
    orig_len = end - OFFSET + 1 if end != -1 else 0
    
    print(f"=== Analysis of offset {hex(OFFSET)} ===\n")
    print(f"Text ends at: {hex(end)}")
    print(f"orig_len (including 0xFF): {orig_len}")
    print(f"offset + orig_len = {hex(OFFSET + orig_len)}")
    
    text = "Sage décision.\\pReste bien loin de cette porte,\\net tu ne le regretteras pas."
    encoded = inject_translations.encode_text(text, value_to_seq)
    print(f"Encoded length: {len(encoded)}")
    
    print(f"\nRange for inner pointer check: {hex(OFFSET + 1)} to {hex(OFFSET + orig_len)}")
    print(f"Does this range include {hex(TARGET)}? {OFFSET + 1 <= TARGET < OFFSET + orig_len}")
    
    if OFFSET + 1 <= TARGET < OFFSET + orig_len:
        print(f"\n*** BUG CONFIRMED! ***")
        print(f"The inner pointer range for {hex(OFFSET)} incorrectly includes {hex(TARGET)}!")
        print(f"This causes the pointer pointing to {hex(TARGET)} to be updated as if it were")
        print(f"an inner pointer of {hex(OFFSET)}.")

if __name__ == "__main__":
    main()
