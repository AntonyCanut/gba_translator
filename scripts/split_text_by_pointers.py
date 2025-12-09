
import sys
from pathlib import Path

# Add scripts dir to path to import inject_translations
sys.path.append(str(Path("scripts").resolve()))

import inject_translations

def main():
    extracted_text_path = Path("extracted_text.txt")
    rom_path = Path("totranslate.gba")
    
    out_with_pointers = Path("text_with_pointers.txt")
    out_without_pointers = Path("text_without_pointers.txt")

    if not extracted_text_path.exists():
        print(f"Error: {extracted_text_path} not found.")
        return
    
    if not rom_path.exists():
        print(f"Error: {rom_path} not found.")
        return

    print("Reading ROM...")
    rom_bytes = rom_path.read_bytes()

    # Build pointer index
    POINTER_BASE = 0x08000000
    pointer_index = set()
    
    print("Building pointer index...")
    for i in range(len(rom_bytes) - 3):
        val = int.from_bytes(rom_bytes[i : i + 4], "little")
        base = val & ~1
        lsb = val & 1
        off = base - POINTER_BASE
        if 0 <= off < len(rom_bytes):
            pointer_index.add(off)
            # Also handle Thumb bit offset (some pointers have LSB=1 but point to text at off+1, or text is at off but pointer has LSB=1)
            # The injection script logic:
            # if lsb == 1 and off + 1 < len(rom_bytes): ...
            # if lsb == 1 and (off + 1) in pointer_index: ...
            # We'll be generous and mark both off and off+1 as "pointed to" if LSB is set, 
            # or just rely on the exact target. 
            # Let's match the injection script's "has_pointer_for" logic more closely.
            # It checks: pointer_index[off], all_pointer_index[off], all_pointer_index[off+1], all_pointer_index[off-1]
            
            # To be safe and simple: if we see a pointer to X, X is pointed.
            # If LSB=1, X (base-base) is pointed.
            pass

    # Re-scan with a more comprehensive approach matching inject_translations.py
    # We want to know if a specific text offset is "reachable" via a pointer.
    
    # Let's build a set of ALL potential targets
    all_targets = set()
    for i in range(len(rom_bytes) - 3):
        val = int.from_bytes(rom_bytes[i : i + 4], "little")
        base = val & ~1
        off = base - POINTER_BASE
        if 0 <= off < len(rom_bytes):
            all_targets.add(off)
            # If it was a thumb pointer, it might be pointing to off, but the text might technically start at off?
            # Or text starts at off, and pointer is off|1.
            # In GBA, LSB=1 usually means Thumb code, but for data it's just the address. 
            # However, `inject_translations.py` checks `off`, `off+1`, `off-1`.
            all_targets.add(off - 1) 
            all_targets.add(off + 1)

    print(f"Found {len(all_targets)} potential pointer targets.")

    print("Processing text entries...")
    with open(extracted_text_path, "r", encoding="utf-8") as f_in, \
         open(out_with_pointers, "w", encoding="utf-8") as f_with, \
         open(out_without_pointers, "w", encoding="utf-8") as f_without:
        
        for line in f_in:
            if ": " not in line:
                continue
            try:
                offset_str, text = line.split(": ", 1)
                offset = int(offset_str, 16)
                
                if offset in all_targets:
                    f_with.write(line)
                else:
                    f_without.write(line)
            except ValueError:
                continue

    print(f"Done. Files created:")
    print(f"- {out_with_pointers}")
    print(f"- {out_without_pointers}")

if __name__ == "__main__":
    main()
