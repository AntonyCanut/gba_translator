
import sys
from pathlib import Path

# Add scripts dir to path to import inject_translations
sys.path.append(str(Path("scripts").resolve()))

import inject_translations

def main():
    charmap_path = Path("charmap_firered.txt")
    fr_path = Path("fr_chunks/chunk_76.txt")
    en_path = Path("origin_chuncks/chunk_76.txt")
    rom_path = Path("totranslate.gba")

    if not charmap_path.exists():
        print(f"Error: {charmap_path} not found.")
        return
    
    if not rom_path.exists():
        print(f"Error: {rom_path} not found.")
        return

    value_to_seq = inject_translations.load_charmap(charmap_path)
    rom_bytes = rom_path.read_bytes()

    # Build pointer index (logic from inject_translations.py)
    POINTER_BASE = 0x08000000
    pointer_index = {}
    
    print("Building pointer index...")
    for i in range(len(rom_bytes) - 3):
        val = int.from_bytes(rom_bytes[i : i + 4], "little")
        base = val & ~1
        lsb = val & 1
        off = base - POINTER_BASE
        if 0 <= off < len(rom_bytes):
            if off not in pointer_index:
                pointer_index[off] = []
            pointer_index[off].append(i)
            # Also handle Thumb bit offset
            if lsb == 1:
                if (off + 1) not in pointer_index:
                    pointer_index[off + 1] = []
                pointer_index[off + 1].append(i)

    def load_entries(path):
        entries = {}
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if ": " not in line:
                continue
            try:
                offset, text = inject_translations.parse_offset_line(line)
                encoded = inject_translations.encode_text(text, value_to_seq)
                entries[offset] = {
                    "text": text,
                    "encoded": encoded,
                    "len": len(encoded),
                    "line": i + 1
                }
            except Exception as e:
                print(f"Error parsing {path} line {i+1}: {e}")
        return entries

    fr_entries = load_entries(fr_path)
    en_entries = load_entries(en_path)

    all_offsets = sorted(fr_entries.keys())
    
    print(f"Checking {len(all_offsets)} offsets...")
    
    issues = []

    for i, offset in enumerate(all_offsets):
        if offset not in en_entries:
            continue
            
        fr_data = fr_entries[offset]
        en_data = en_entries[offset]
        
        if i < len(all_offsets) - 1:
            next_offset = all_offsets[i+1]
            gap = next_offset - offset
        else:
            gap = 999999
            
        fr_len = fr_data["len"]
        en_len = en_data["len"]
        
        has_pointer = offset in pointer_index and len(pointer_index[offset]) > 0
        
        # Check for overflow
        if fr_len > gap:
            # If it has a pointer, it CAN be relocated, so it's not necessarily a hard overflow crash
            # UNLESS the script fails to relocate it.
            # But if it does NOT have a pointer, it MUST fit in place.
            
            if not has_pointer:
                issues.append({
                    "type": "CRITICAL: NO POINTER & OVERFLOW",
                    "offset": offset,
                    "fr_len": fr_len,
                    "gap": gap,
                    "text": fr_data["text"]
                })
            else:
                # It has a pointer, so it should be relocated.
                # However, if it's a "Tight Fit" (en_len == gap) and we exceed it, it might still be risky if the game expects fixed size.
                pass

        # Check for "Tight Fit" specifically
        if fr_len > en_len and en_len == gap:
             if not has_pointer:
                 issues.append({
                    "type": "CRITICAL: TIGHT FIT & NO POINTER",
                    "offset": offset,
                    "fr_len": fr_len,
                    "en_len": en_len,
                    "gap": gap,
                    "text": fr_data["text"]
                })

    if not issues:
        print("No CRITICAL un-relocatable overflows found.")
    else:
        print(f"Found {len(issues)} CRITICAL issues:")
        for issue in issues:
            print(f"[{issue['type']}] Offset {hex(issue['offset'])}")
            print(f"  Gap: {issue['gap']}, FR Len: {issue['fr_len']}")
            print(f"  Text: {issue['text']}")
            print("-" * 40)

if __name__ == "__main__":
    main()
