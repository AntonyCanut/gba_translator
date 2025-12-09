#!/usr/bin/env python3
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Filter a text file to keep only lines pointed to by the ROM.")
    parser.add_argument("--input", type=Path, required=True, help="Input text file (offset: text)")
    parser.add_argument("--rom", type=Path, required=True, help="ROM file (.gba)")
    parser.add_argument("--output", type=Path, required=True, help="Output filtered text file")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} not found.")
        return
    
    if not args.rom.exists():
        print(f"Error: {args.rom} not found.")
        return

    print("Reading ROM...")
    rom_bytes = args.rom.read_bytes()

    # Build pointer index
    POINTER_BASE = 0x08000000
    all_targets = set()
    
    print("Building pointer index...")
    for i in range(len(rom_bytes) - 3):
        val = int.from_bytes(rom_bytes[i : i + 4], "little")
        base = val & ~1
        off = base - POINTER_BASE
        if 0 <= off < len(rom_bytes):
            all_targets.add(off)
            # Be generous with Thumb pointers or off-by-one text starts
            all_targets.add(off - 1) 
            all_targets.add(off + 1)

    print(f"Found {len(all_targets)} potential pointer targets.")

    print(f"Filtering {args.input}...")
    kept_count = 0
    total_count = 0
    
    with args.input.open("r", encoding="utf-8") as f_in, \
         args.output.open("w", encoding="utf-8") as f_out:
        
        for line in f_in:
            if ": " not in line:
                continue
            try:
                offset_str, _ = line.split(": ", 1)
                offset = int(offset_str, 16)
                total_count += 1
                
                if offset in all_targets:
                    f_out.write(line)
                    kept_count += 1
            except ValueError:
                continue

    print(f"Done. Kept {kept_count} out of {total_count} entries.")
    print(f"Output written to {args.output}")

if __name__ == "__main__":
    main()
