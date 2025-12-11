#!/usr/bin/env python3
"""
Check the pointer value BEFORE and AFTER injection
"""

import struct
from pathlib import Path

ORIG_ROM = Path("totranslate.gba")
NEW_ROM = Path("totranslate_test.gba")
POINTER_BASE = 0x08000000

TARGET = 0x1F2D1D7
POINTER_LOC = 0x1E902E1

def main():
    orig = ORIG_ROM.read_bytes()
    new = NEW_ROM.read_bytes()
    
    print(f"=== Pointer at {hex(POINTER_LOC)} ===\n")
    
    orig_ptr = struct.unpack("<I", orig[POINTER_LOC:POINTER_LOC+4])[0]
    orig_target = orig_ptr - POINTER_BASE
    print(f"ORIGINAL ROM: pointer = {hex(orig_ptr)} -> target = {hex(orig_target)}")
    
    new_ptr = struct.unpack("<I", new[POINTER_LOC:POINTER_LOC+4])[0]
    new_target = new_ptr - POINTER_BASE
    print(f"NEW ROM: pointer = {hex(new_ptr)} -> target = {hex(new_target)}")
    
    if orig_target == TARGET:
        print(f"\nOriginal pointer correctly points to {hex(TARGET)}")
    else:
        print(f"\nOriginal pointer does NOT point to {hex(TARGET)}!")
        print(f"It points to {hex(orig_target)} instead!")
    
    if new_target == TARGET:
        print(f"New pointer correctly points to {hex(TARGET)}")
    else:
        print(f"New pointer INCORRECTLY points to {hex(new_target)}, not {hex(TARGET)}!")

if __name__ == "__main__":
    main()
