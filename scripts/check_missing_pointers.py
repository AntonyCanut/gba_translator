#!/usr/bin/env python3
"""
Check if pointers exist for specific offsets that are reported as "sans pointeur".
"""

import struct
from pathlib import Path

ROM_PATH = Path("totranslate.gba")
POINTER_BASE = 0x08000000

# Offsets from the error messages
OFFSETS_TO_CHECK = [
    0x7e722a,
    0x74ae89,
    0x8d160c,
    0x7e95c0,
    0x7e96b2,
    0x7e7553,
]

def main():
    rom = ROM_PATH.read_bytes()
    
    for target_offset in OFFSETS_TO_CHECK:
        pointer_val = POINTER_BASE + target_offset
        pointer_bytes = struct.pack("<I", pointer_val)
        
        # Search for exact pointer
        positions = []
        pos = 0
        while True:
            pos = rom.find(pointer_bytes, pos)
            if pos == -1:
                break
            positions.append(pos)
            pos += 1
        
        # Also check with Thumb bit (LSB=1)
        pointer_val_thumb = pointer_val | 1
        pointer_bytes_thumb = struct.pack("<I", pointer_val_thumb)
        thumb_positions = []
        pos = 0
        while True:
            pos = rom.find(pointer_bytes_thumb, pos)
            if pos == -1:
                break
            thumb_positions.append(pos)
            pos += 1
        
        print(f"Offset {hex(target_offset)}:")
        if positions:
            print(f"  Found {len(positions)} pointer(s) at: {[hex(p) for p in positions[:5]]}")
        else:
            print(f"  No direct pointer found")
        if thumb_positions:
            print(f"  Found {len(thumb_positions)} Thumb pointer(s) at: {[hex(p) for p in thumb_positions[:5]]}")
        
        # Check +/- 1 offset
        for delta in [-1, 1]:
            alt_offset = target_offset + delta
            alt_pointer = POINTER_BASE + alt_offset
            alt_bytes = struct.pack("<I", alt_pointer)
            alt_pos = rom.find(alt_bytes)
            if alt_pos != -1:
                print(f"  Found pointer to {hex(alt_offset)} (delta {delta}) at {hex(alt_pos)}")
        
        print()

if __name__ == "__main__":
    main()
