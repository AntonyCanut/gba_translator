import struct
from pathlib import Path
from collections import Counter

def load_text_locations(path: Path):
    locations = {}
    if not path.exists():
        return locations
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if ": " in line:
                offset_str, _ = line.split(": ", 1)
                offset = int(offset_str, 16)
                locations[offset] = True
    return locations

def main():
    rom_path = Path("../totranslate.gba")
    text_locs_path = Path("../extracted_text.txt")
    
    with open(rom_path, "rb") as f:
        data = f.read()
        
    text_offsets = sorted(load_text_locations(text_locs_path).keys())
    text_ranges = []
    
    # Estimate lengths (naive)
    for i in range(len(text_offsets)):
        start = text_offsets[i]
        if i < len(text_offsets) - 1:
            end = text_offsets[i+1]
        else:
            end = len(data)
        
        # Refine end by looking for FF
        # (This is approximate, but good enough for finding inner pointers)
        # Actually, let's just use the "next text start" as the upper bound
        # But we only care about pointers pointing *inside* a text block.
        
        # Let's find the FF terminator for this text
        term = data.find(b"\xff", start)
        if term != -1 and term < end:
            real_end = term + 1
        else:
            real_end = min(end, start + 1000) # Cap at 1000 chars
            
        text_ranges.append((start, real_end))

    # Scan for pointers
    print("Scanning for pointers...")
    pointers = []
    for i in range(0, len(data), 4):
        val = struct.unpack("<I", data[i:i+4])[0]
        if 0x08000000 <= val < 0x08000000 + len(data):
            target = val - 0x08000000
            pointers.append(target)
            
    # Check intersections
    print("Analyzing intersections...")
    byte_before_counter = Counter()
    
    # Optimize: Sort ranges
    # For each pointer, check if it falls in any range
    # Since ranges are sorted, we can use binary search or just iterate efficiently
    
    # Create a map of "covered bytes" to speed up? No, ROM is 32MB.
    # Let's just iterate pointers and check against ranges.
    # To be fast:
    # 1. Sort pointers.
    # 2. Iterate pointers and ranges together.
    
    pointers.sort()
    
    range_idx = 0
    inner_ptrs_count = 0
    
    for ptr in pointers:
        # Advance ranges that end before ptr
        while range_idx < len(text_ranges) and text_ranges[range_idx][1] <= ptr:
            range_idx += 1
            
        if range_idx >= len(text_ranges):
            break
            
        start, end = text_ranges[range_idx]
        
        # Check if ptr is inside [start+1, end]
        # We exclude start because that's a normal pointer.
        if start < ptr < end:
            # Found inner pointer!
            byte_before = data[ptr - 1]
            byte_before_counter[byte_before] += 1
            inner_ptrs_count += 1
            
    print(f"Found {inner_ptrs_count} inner pointers.")
    print("Top 10 Bytes Before Pointer:")
    for byte_val, count in byte_before_counter.most_common(10):
        print(f"0x{byte_val:02X}: {count}")

if __name__ == "__main__":
    main()
