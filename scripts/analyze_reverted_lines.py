#!/usr/bin/env python3
import sys

def main():
    rom_path = "totranslate.gba"
    fr_file = "fr_chunks/chunk_54.txt.bak"
    en_file = "origin_chuncks/chunk_54.txt"
    charmap_path = "charmap_firered.txt"
    
    # Load charmap (simplified)
    charmap = {}
    with open(charmap_path, "r") as f:
        for line in f:
            if "=" in line:
                key, val = line.strip().split("=", 1)
                if key.startswith("'") and key.endswith("'"):
                    key = key[1:-1]
                else:
                    key = "{" + key + "}"
                val_part = val.split()[0]
                if val_part.startswith("'") and val_part.endswith("'"):
                     pass
                else:
                     try:
                        charmap[key] = int(val_part, 16)
                     except ValueError:
                        pass

    # Load ROM
    with open(rom_path, "rb") as f:
        rom_data = f.read()

    # Build pointer index
    pointers = set()
    for i in range(0, len(rom_data) - 4, 4):
        val = int.from_bytes(rom_data[i:i+4], "little")
        if 0x08000000 <= val < 0x08000000 + len(rom_data):
            offset = val - 0x08000000
            pointers.add(offset)

    with open(fr_file, "r") as f:
        fr_lines = f.readlines()
        
    print(f"{'Offset':<12} | {'Orig':<5} | {'New':<5} | {'Diff':<5} | {'Text Preview'}")
    print("-" * 80)
    
    for line in fr_lines:
        if ": " not in line:
            continue
            
        offset_str, text = line.split(": ", 1)
        offset = int(offset_str, 16)
        text = text.strip()
        
        end = rom_data.find(b"\xFF", offset)
        if end == -1: continue
        orig_len = end - offset + 1
        
        # Calc encoded len
        encoded_len = 0
        j = 0
        while j < len(text):
            if text[j] == "{" and "}" in text[j:]:
                end_tok = text.find("}", j)
                token = text[j:end_tok+1]
                if token == "{COLOR}":
                    encoded_len += 2 
                    j = end_tok + 1
                elif token.startswith("{STR_VAR"):
                    encoded_len += 2
                    j = end_tok + 1
                else:
                    encoded_len += 1
                    j = end_tok + 1
            elif text[j] == "\\":
                encoded_len += 1
                j += 2
            else:
                encoded_len += 1
                j += 1
        encoded_len += 1
        
        diff = encoded_len - orig_len
        has_ptr = offset in pointers
        
        if diff > 0 and not has_ptr:
            print(f"{offset_str:<12} | {orig_len:<5} | {encoded_len:<5} | {diff:<5} | {text[:40]}...")

if __name__ == "__main__":
    main()
