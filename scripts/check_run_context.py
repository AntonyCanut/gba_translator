#!/usr/bin/env python3
"""
Check if offset 0x1F2D1D7 is part of a run that was relocated.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import inject_translations
import struct

ROM_PATH = Path("totranslate.gba")
CHARMAP_PATH = Path("charmap_firered.txt")
TEXT_FILE = Path("fr_chunks/chunk_76.txt")

TARGET_OFFSET = 0x1F2D1D7

def main():
    rom = ROM_PATH.read_bytes()
    
    # Find the text before and after this offset
    print(f"=== Checking run context for {hex(TARGET_OFFSET)} ===\n")
    
    # Find the 0xFF terminator before this offset (previous text end)
    prev_ff = TARGET_OFFSET - 1
    while prev_ff > 0 and rom[prev_ff] != 0xFF:
        prev_ff -= 1
    
    print(f"Previous 0xFF at: {hex(prev_ff)}")
    print(f"Gap between prev FF and target: {TARGET_OFFSET - prev_ff - 1} bytes")
    
    if TARGET_OFFSET - prev_ff == 1:
        print("This text starts right after the previous one's terminator!")
        print("It might be grouped into a RUN with other texts.\n")
        
        # Find the start of this run
        run_start = prev_ff
        while run_start > 0:
            # Check for 0xFF before
            if rom[run_start - 1] == 0xFF:
                # Check if there's a gap (more than just 1 FF)
                ff_count = 0
                check_pos = run_start - 1
                while check_pos > 0 and rom[check_pos] == 0xFF:
                    ff_count += 1
                    check_pos -= 1
                if ff_count > 1:
                    break  # Found a gap of FFs, this is the run boundary
            # Keep going back
            run_start -= 1
            # Stop at a reasonable limit
            if prev_ff - run_start > 5000:
                break
        
        # Find the end of this text
        text_end = rom.find(b'\xff', TARGET_OFFSET)
        original_len = text_end - TARGET_OFFSET + 1 if text_end != -1 else 0
        print(f"Original text ends at: {hex(text_end)} (length: {original_len})")
        
        # Check what text is after this one
        next_text_start = text_end + 1
        if next_text_start < len(rom) and rom[next_text_start] != 0xFF:
            next_text_end = rom.find(b'\xff', next_text_start)
            print(f"Next text starts at: {hex(next_text_start)}")
            
    # Check what's in the chunk file around this offset
    print("\n=== Nearby texts in chunk file ===")
    lines = TEXT_FILE.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if ": " not in line:
            continue
        offset_str, text = line.split(": ", 1)
        offset = int(offset_str, 16)
        if abs(offset - TARGET_OFFSET) < 500:
            print(f"Line {i+1}: {offset_str} - {text[:40]}...")

if __name__ == "__main__":
    main()
