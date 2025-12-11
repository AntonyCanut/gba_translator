#!/usr/bin/env python3
"""
Check what offset the pointer at 0x1E902E1 is indexed under in all_pointer_index
"""

import struct
from pathlib import Path

ROM_PATH = Path("totranslate.gba")
POINTER_BASE = 0x08000000
MIN_VALID_OFFSET = 0x100

POINTER_LOC = 0x1E902E1
TARGET = 0x1F2D1D7
TEST_OFFSET = 0x1F2D192

def main():
    rom = ROM_PATH.read_bytes()
    
    # Build all_pointer_index to see how this pointer is indexed
    all_pointer_index = {}
    for i in range(len(rom) - 3):
        val = int.from_bytes(rom[i:i+4], "little")
        base = val & ~1
        lsb = val & 1
        off = base - POINTER_BASE
        if MIN_VALID_OFFSET <= off < len(rom):
            all_pointer_index.setdefault(off, []).append((i, lsb))
            if lsb == 1 and off + 1 < len(rom):
                all_pointer_index.setdefault(off + 1, []).append((i, lsb))
    
    print(f"=== Checking how pointer at {hex(POINTER_LOC)} is indexed ===\n")
    
    # What offset does this pointer originally point to?
    ptr_val = struct.unpack("<I", rom[POINTER_LOC:POINTER_LOC+4])[0]
    ptr_target = ptr_val - POINTER_BASE
    lsb = ptr_val & 1
    print(f"Pointer value: {hex(ptr_val)}")
    print(f"Points to: {hex(ptr_target)}")
    print(f"LSB (Thumb bit): {lsb}")
    
    # Check if pointer is indexed under different offsets
    print(f"\nPointer at {hex(POINTER_LOC)} is indexed under:")
    for off, locs in all_pointer_index.items():
        for loc, l in locs:
            if loc == POINTER_LOC:
                print(f"  {hex(off)} (lsb={l})")
    
    # Check the range for TEST_OFFSET
    end = rom.find(b"\xff", TEST_OFFSET)
    orig_len = end - TEST_OFFSET + 1 if end != -1 else 0
    print(f"\nFor offset {hex(TEST_OFFSET)}:")
    print(f"  orig_len = {orig_len}")
    print(f"  inner pointer range: {hex(TEST_OFFSET + 1)} to {hex(TEST_OFFSET + orig_len - 1)}")
    
    # Check which offsets in the range have ptr_target indexed
    print(f"\nWhich offsets in range [{hex(TEST_OFFSET + 1)}, {hex(TEST_OFFSET + orig_len)}) have {hex(ptr_target)} indexed?")
    for check_off in range(TEST_OFFSET + 1, TEST_OFFSET + orig_len):
        if check_off in all_pointer_index:
            for loc, l in all_pointer_index[check_off]:
                if loc == POINTER_LOC:
                    print(f"  {hex(check_off)}: YES! This is where {hex(POINTER_LOC)} is indexed")

if __name__ == "__main__":
    main()
