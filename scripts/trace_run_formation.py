#!/usr/bin/env python3
"""
Trace exactly how 0x1F2D1D7 is being grouped into runs.
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
    
    # Order offsets
    ordered_offsets = sorted(entries_by_offset.keys())
    
    # Build original_lengths
    original_lengths = {}
    for off in ordered_offsets:
        end = rom.find(b"\xff", off)
        if end != -1:
            original_lengths[off] = end - off + 1
    
    # Trace run formation
    print(f"=== Tracing run formation for {hex(TARGET)} ===\n")
    
    anchor_for = {}
    run_members = {}
    prev_offset = None
    current_anchor = None
    
    for off in ordered_offsets:
        is_target = (off == TARGET)
        
        if prev_offset is None or off != prev_offset + original_lengths[prev_offset]:
            current_anchor = None
            if abs(off - TARGET) < 2000:
                print(f"  {hex(off)}: New run (gap from prev)")
        
        has_ptr = has_pointer_for(off)
        if has_ptr:
            current_anchor = off
            if abs(off - TARGET) < 2000:
                print(f"  {hex(off)}: Has pointer, becomes anchor")
        
        if current_anchor is not None:
            anchor_for[off] = current_anchor
            run_members.setdefault(current_anchor, []).append(off)
            if is_target:
                print(f"  {hex(off)}: *** TARGET added to run anchored at {hex(current_anchor)}")
        
        prev_offset = off
    
    # Find TARGET's run
    target_anchor = anchor_for.get(TARGET)
    if target_anchor:
        print(f"\nTARGET {hex(TARGET)} is in run anchored at {hex(target_anchor)}")
        run = run_members[target_anchor]
        print(f"Run members: {[hex(o) for o in run]}")
        
        # Check group_runs criteria
        print(f"\nGroup runs criteria check:")
        for o in run:
            ent = entries_by_offset[o]
            too_long = ent["enc_len"] > ent["orig_len"]
            has_ptr = has_pointer_for(o)
            triggers_group = too_long and not has_ptr
            print(f"  {hex(o)}: enc={ent['enc_len']}, orig={ent['orig_len']}, "
                  f"too_long={too_long}, has_ptr={has_ptr}, triggers_group={triggers_group}")
    else:
        print(f"TARGET {hex(TARGET)} has no anchor (not in a run)")

if __name__ == "__main__":
    main()
