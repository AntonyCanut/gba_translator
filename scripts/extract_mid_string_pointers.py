#!/usr/bin/env python3
import struct
from pathlib import Path
from typing import Dict, List, Tuple

# Configuration
ROM_PATH = Path("../totranslate.gba")
TEXT_FILE = Path("../extracted_text.txt")
FR_CHUNKS_DIR = Path("../fr_chunks")
VO_CHUNKS_DIR = Path("../origin_chuncks")
POINTER_BASE = 0x08000000

def load_chunk_map(directory: Path) -> Dict[int, str]:
    """Scans a directory of chunk files and returns {offset: 'filename:line'}."""
    mapping = {}
    if not directory.exists():
        return mapping
    
    for file_path in directory.glob("*.txt"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    if ": " in line:
                        parts = line.split(": ", 1)
                        try:
                            offset = int(parts[0], 16)
                            mapping[offset] = f"{file_path.name}:{line_no}"
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
    return mapping

def main():
    if not ROM_PATH.exists():
        print(f"Error: {ROM_PATH} not found.")
        return
    if not TEXT_FILE.exists():
        print(f"Error: {TEXT_FILE} not found.")
        return

    print(f"Loading {ROM_PATH}...")
    rom_bytes = ROM_PATH.read_bytes()

    # Load chunk maps
    print("Loading chunk maps...")
    fr_map = load_chunk_map(FR_CHUNKS_DIR)
    vo_map = load_chunk_map(VO_CHUNKS_DIR)

    # 1. Load known text offsets and lengths
    print(f"Loading text locations from {TEXT_FILE}...")
    text_ranges: List[Tuple[int, int, str]] = [] # (start, end, text_preview)
    
    for line in TEXT_FILE.read_text(encoding="utf-8").splitlines():
        if ": " not in line:
            continue
        try:
            off_str, text = line.split(": ", 1)
            start = int(off_str, 16)
        except ValueError:
            continue
            
        if start >= len(rom_bytes):
            continue
            
        # Find end (0xFF)
        end = rom_bytes.find(b"\xFF", start)
        if end == -1:
            continue
        
        # We consider the range [start, end] (inclusive of 0xFF for safety, but pointers usually point to char)
        # Length includes 0xFF
        length = end - start + 1
        text_ranges.append((start, start + length, text))

    # 2. Scan for all pointers in ROM
    print("Scanning ROM for pointers...")
    pointers: Dict[int, List[int]] = {} # target_offset -> list of locations where pointer exists
    
    for i in range(0, len(rom_bytes) - 3, 4): # Pointers are 4-byte aligned usually, but let's check every 4 bytes
        # Optimization: checking every byte is slow in Python. 
        # GBA pointers are usually 4-byte aligned in data tables, but can be unaligned in code (ldr).
        # For text pointers (tables), 4-byte alignment is standard.
        val = int.from_bytes(rom_bytes[i : i + 4], "little")
        
        # Check if it looks like a ROM pointer (0x08XXXXXX)
        if 0x08000000 <= val <= 0x09FFFFFF:
            target = (val & ~1) - POINTER_BASE # Strip Thumb bit
            if 0 <= target < len(rom_bytes):
                if target not in pointers:
                    pointers[target] = []
                pointers[target].append(i)

    # 3. Find intersections
    print("Analyzing intersections...")
    found_count = 0
    
    # Sort ranges by start to make it easier? Not strictly necessary if we just iterate.
    # For each text block, check if there are pointers pointing inside it (start < p < end)
    
    results = []

    for start, end, text in text_ranges:
        inner_pointers = []
        # Check every byte offset inside the string
        # We skip 'start' because that's a normal pointer to the string.
        # We skip 'end' because that's usually the next string or just 0xFF.
        for p in range(start + 1, end):
            if p in pointers:
                inner_pointers.append(p)
        
        if inner_pointers:
            found_count += 1
            entry = {
                "offset": start,
                "text": text,
                "inner_pointers": []
            }
            for p in inner_pointers:
                # Get the text starting at this inner pointer to show context
                sub_text_end = rom_bytes.find(b"\xFF", p)
                sub_text = ""
                if sub_text_end != -1:
                    # decoding is hard without charmap, let's just show hex or try simple ascii
                    # We can try to match it with the substring of the original text if possible
                    # But 'text' variable is already decoded.
                    # Let's just calculate the index in the string.
                    pass
                
                entry["inner_pointers"].append({
                    "target": p,
                    "sources": pointers[p],
                    "relative_index": p - start
                })
            results.append(entry)

    # 4. Report
    print(f"\nFound {len(results)} texts with mid-string pointers.\n")
    
    for res in results:
        off = res["offset"]
        text = res["text"]
        
        fr_source = fr_map.get(off, "Unknown")
        vo_source = vo_map.get(off, "Unknown")
        
        print(f"=== Text at {hex(off)} ===")
        print(f"  FR Source: {fr_source}")
        print(f"  VO Source: {vo_source}")
        print(f"Content: {text[:60]}{'...' if len(text)>60 else ''}")
        for inner in res["inner_pointers"]:
            tgt = inner["target"]
            rel = inner["relative_index"]
            srcs = [hex(s) for s in inner["sources"]]
            print(f"  -> Inner Pointer at {hex(tgt)} (+{rel}) referenced at: {', '.join(srcs)}")
            # Try to show where it points in the text
            # This is approximate because 'text' is decoded and might not match byte-for-byte with control codes
            # But it gives an idea.
            print(f"     (Points roughly to byte index {rel} of the raw data)")
        print("")

if __name__ == "__main__":
    main()
