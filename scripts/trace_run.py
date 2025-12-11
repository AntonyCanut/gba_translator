#!/usr/bin/env python3
"""
Trace the exact run processing for the problematic text block.
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

TARGET = 0x1F2D1D7

def main():
    rom = ROM_PATH.read_bytes()
    value_to_seq = inject_translations.load_charmap(CHARMAP_PATH)
    
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
            entries_by_offset[offset] = {
                "text": text,
                "encoded": encoded,
                "len": len(encoded)
            }
        except Exception as e:
            print(f"Error encoding {offset_str}: {e}")
    
    print(f"Loaded {len(entries_by_offset)} entries from chunk file.\n")
    
    # Find run containing TARGET
    # Look for adjacent texts
    
    # Get original lengths
    original_lengths = {}
    for offset in entries_by_offset.keys():
        if offset >= len(rom):
            continue
        end = rom.find(b"\xff", offset)
        if end != -1:
            original_lengths[offset] = end - offset + 1
    
    # Find texts adjacent to TARGET
    sorted_offsets = sorted(entries_by_offset.keys())
    
    print(f"=== Finding run containing {hex(TARGET)} ===\n")
    
    # Find texts in same contiguous block
    run_texts = []
    for offset in sorted_offsets:
        if offset not in original_lengths:
            continue
        orig_end = offset + original_lengths[offset] - 1  # Position of 0xFF
        next_offset = orig_end + 1
        
        # Check if another text starts right after
        if next_offset in entries_by_offset:
            if offset not in run_texts:
                run_texts.append(offset)
            if next_offset not in run_texts:
                run_texts.append(next_offset)
    
    # Check if TARGET is in run_texts
    if TARGET in run_texts:
        print(f"TARGET {hex(TARGET)} is in a run!")
    else:
        # TARGET might be AFTER a text in the run
        for offset in sorted_offsets:
            if offset not in original_lengths:
                continue
            orig_end = offset + original_lengths[offset] - 1
            if orig_end + 1 == TARGET:
                print(f"TARGET {hex(TARGET)} starts after {hex(offset)} ends")
                run_texts.append(TARGET)
    
    run_texts = sorted(set(run_texts))
    
    # Show the run
    print("\n=== Run contents ===")
    for i, offset in enumerate(run_texts):
        if abs(offset - TARGET) < 1000:
            orig_len = original_lengths.get(offset, "?")
            new_len = len(entries_by_offset[offset]["encoded"]) if offset in entries_by_offset else "N/A"
            in_chunk = offset in entries_by_offset
            print(f"{i}: {hex(offset)} - orig_len={orig_len}, new_len={new_len}, in_chunk={in_chunk}")
            if offset == TARGET:
                print(f"   ^^^ THIS IS THE TARGET")
    
    # Simulate run relocation
    print("\n=== Simulating new offset calculation ===")
    
    # Find the run anchor (first offset)
    run_start = min([o for o in run_texts if abs(o - TARGET) < 2000])
    dest_offset = 0x1F2EA3C  # From the actual analysis (where the run was written)
    
    print(f"Run anchor: {hex(run_start)}")
    print(f"Destination: {hex(dest_offset)}")
    
    curr_new_rel = 0
    for offset in sorted([o for o in run_texts if o >= run_start and abs(o - TARGET) < 2000]):
        new_abs = dest_offset + curr_new_rel
        print(f"  {hex(offset)}: New location would be {hex(new_abs)}")
        
        # Advance by the LENGTH OF THE NEW TEXT if in entries, else by original length
        if offset in entries_by_offset:
            advance = len(entries_by_offset[offset]["encoded"])
        else:
            advance = original_lengths.get(offset, 0)
        
        print(f"    Advance by: {advance} (in_chunk={offset in entries_by_offset})")
        curr_new_rel += advance
        
        if offset == TARGET:
            print(f"    ^^^ TARGET - actual text is at {hex(TARGET)}")

if __name__ == "__main__":
    main()
