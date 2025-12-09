#!/usr/bin/env python3
import sys
import struct
from pathlib import Path

def main():
    rom_path = "totranslate.gba"
    fr_file = "fr_chunks/chunk_54.txt.bak"
    en_file = "origin_chuncks/chunk_54.txt"
    out_file = "fr_chunks/chunk_54.txt"
    charmap_path = "charmap_firered.txt"
    
    # Load charmap
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
            
    # Read files
    with open(fr_file, "r") as f:
        fr_lines = f.readlines()
    with open(en_file, "r") as f:
        en_lines = f.readlines()
        
    # Parse into dicts
    fr_dict = {}
    for line in fr_lines:
        if ": " in line:
            off, txt = line.split(": ", 1)
            fr_dict[off] = txt.strip()
            
    en_dict = {}
    for line in en_lines:
        if ": " in line:
            off, txt = line.split(": ", 1)
            en_dict[off] = txt.strip()
            
    # Process
    out_lines = []
    reverted_count = 0
    
    # We iterate through the FR lines to preserve order/structure if possible, 
    # but actually we should probably iterate through offsets found in FR file.
    
    for line in fr_lines:
        if ": " not in line:
            out_lines.append(line)
            continue
            
        offset_str, text = line.split(": ", 1)
        offset = int(offset_str, 16)
        text = text.strip()
        
        # Calculate original length
        end = rom_data.find(b"\xFF", offset)
        if end == -1:
            out_lines.append(line)
            continue
        orig_len = end - offset + 1
        
        # Calculate encoded length (approx)
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
        encoded_len += 1 # Terminator
        
        diff = encoded_len - orig_len
        has_ptr = offset in pointers
        
        if diff > 0 and not has_ptr:
            # DANGER! Revert to English
            if offset_str in en_dict:
                print(f"Reverting {offset_str} due to overflow ({encoded_len} > {orig_len}) and no pointer.")
                out_lines.append(f"{offset_str}: {en_dict[offset_str]}\n")
                reverted_count += 1
            else:
                print(f"Warning: Could not find English original for {offset_str}, keeping French.")
                out_lines.append(line)
        else:
            out_lines.append(line)
            
    with open(out_file, "w") as f:
        f.writelines(out_lines)
        
    print(f"Done. Reverted {reverted_count} lines.")

if __name__ == "__main__":
    main()
