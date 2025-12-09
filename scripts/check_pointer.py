#!/usr/bin/env python3
import sys
import struct

def main():
    rom_path = "totranslate.gba"
    offsets = [0x1F26B23, 0x1F26B32, 0x1F26B42]
    
    with open(rom_path, "rb") as f:
        data = f.read()
    
    for target_offset in offsets:
        pointer_val = 0x08000000 + target_offset
        pointer_bytes = struct.pack("<I", pointer_val)
        
        print(f"Searching for pointer {hex(pointer_val)} ({pointer_bytes.hex()})...")
        
        count = 0
        offset = 0
        while True:
            offset = data.find(pointer_bytes, offset)
            if offset == -1:
                break
            print(f"Found at {hex(offset)}")
            count += 1
            offset += 1
            
        print(f"Total found for {hex(target_offset)}: {count}")
        print("-" * 20)

if __name__ == "__main__":
    main()
