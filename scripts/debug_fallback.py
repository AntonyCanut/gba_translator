#!/usr/bin/env python3
"""
Debug: Find which entry triggers the fallback run that includes 0x1F2D1D7
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import inject_translations
import struct

ROM_PATH = Path("totranslate.gba")
CHARMAP_PATH = Path("charmap_firered.txt")
TEXT_FILE = Path("fr_chunks/chunk_76.txt")
POINTER_BASE = 0x08000000
MIN_VALID_OFFSET = 0x100

TARGET = 0x1F2D1D7

def main():
    rom = ROM_PATH.read_bytes()
    rom_bytes = bytearray(rom)
    value_to_seq = inject_translations.load_charmap(CHARMAP_PATH)
    
    # Build pointer index
    all_pointer_index = {}
    for i in range(len(rom) - 3):
        val = int.from_bytes(rom[i:i+4], "little")
        base = val & ~1
        lsb = val & 1
        off = base - POINTER_BASE
        if MIN_VALID_OFFSET <= off < len(rom):
            all_pointer_index.setdefault(off, []).append((i, lsb))
    
    def has_pointer_for(off):
        if all_pointer_index.get(off):
            return True
        if all_pointer_index.get(off + 1):
            return True
        if all_pointer_index.get(off - 1):
            return True
        return False
    
    def collect_contiguous_run(start_off):
        run_start = start_off
        while True:
            prev_term = rom_bytes.rfind(b"\xff", 0, run_start)
            if prev_term == -1:
                break
            prev_prev_term = rom_bytes.rfind(b"\xff", 0, prev_term)
            prev_start = (prev_prev_term + 1) if prev_prev_term != -1 else 0
            prev_end = rom_bytes.find(b"\xff", prev_start)
            if prev_end == -1 or prev_end + 1 != run_start:
                break
            run_start = prev_start
        
        run = []
        pos = run_start
        while pos < len(rom_bytes):
            end = rom_bytes.find(b"\xff", pos)
            if end == -1:
                break
            run.append((pos, end - pos + 1))
            next_start = end + 1
            if next_start >= len(rom_bytes) or rom_bytes[next_start] == 0xFF:
                break
            pos = next_start
        return run
    
    # Load texts from chunk
    lines = TEXT_FILE.read_text(encoding="utf-8").splitlines()
    entries_by_offset = {}
    for line in lines:
        if ": " not in line:
            continue
        offset_str, text = line.split(": ", 1)
        offset = int(offset_str, 16)
        try:
            encoded = inject_translations.encode_text(text, value_to_seq)
            end = rom.find(b"\xff", offset)
            orig_len = end - offset + 1 if end != -1 else 0
            entries_by_offset[offset] = {
                "text": text,
                "encoded": encoded,
                "enc_len": len(encoded),
                "orig_len": orig_len
            }
        except Exception as e:
            print(f"Error encoding {offset_str}: {e}")
    
    # Simulate the fallback run logic
    print(f"=== Finding which entry triggers fallback run including {hex(TARGET)} ===\n")
    
    for offset, ent in entries_by_offset.items():
        enc_len = ent["enc_len"]
        orig_len = ent["orig_len"]
        
        # Skip if fits in place
        if enc_len <= orig_len:
            continue
        
        # Check if has pointer
        if has_pointer_for(offset):
            continue
        
        # This entry would trigger the fallback run logic!
        run_segments = collect_contiguous_run(offset)
        run_offsets = [o for o, l in run_segments]
        
        if TARGET in run_offsets:
            print(f"FOUND! Entry at {hex(offset)} (enc={enc_len}, orig={orig_len}) triggers fallback run")
            print(f"Fallback run contains: {[hex(o) for o in run_offsets[:20]]}...")
            print(f"Target {hex(TARGET)} is in this run!")
            
            # Check if any offset in the run has a pointer
            anchor_in_run = None
            for off_seg, _ in run_segments:
                if has_pointer_for(off_seg):
                    anchor_in_run = off_seg
                    break
            
            if anchor_in_run:
                print(f"Anchor found at: {hex(anchor_in_run)}")
            else:
                print("No anchor found in run!")
            
            return
    
    print(f"No entry triggers a fallback run containing {hex(TARGET)}")
    print("The issue might be elsewhere...")

if __name__ == "__main__":
    main()
