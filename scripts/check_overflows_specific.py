#!/usr/bin/env python3
import sys
import struct
from pathlib import Path

def main():
    rom_path = "totranslate.gba"
    text_file = "fr_chunks/chunk_54.txt"
    charmap_path = "charmap_firered.txt"
    
    # Load charmap
    charmap = {}
    with open(charmap_path, "r") as f:
        for line in f:
            if "=" in line:
                key, val = line.strip().split("=", 1)
                # Handle simple cases
                if key.startswith("'") and key.endswith("'"):
                    key = key[1:-1]
                else:
                    key = "{" + key + "}"
                
                val_part = val.split()[0]
                if val_part.startswith("'") and val_part.endswith("'"):
                     # Handle case where value is a char literal? Unlikely in this format but possible
                     pass
                else:
                     try:
                        charmap[key] = int(val_part, 16)
                     except ValueError:
                        pass
    
    # Load ROM
    with open(rom_path, "rb") as f:
        rom_data = f.read()
        
    # Build pointer index (simple)
    pointers = set()
    for i in range(0, len(rom_data) - 4, 4):
        val = int.from_bytes(rom_data[i:i+4], "little")
        if 0x08000000 <= val < 0x08000000 + len(rom_data):
            offset = val - 0x08000000
            pointers.add(offset)
            
    print(f"Loaded {len(pointers)} pointers.")
    
    # Check file
    with open(text_file, "r") as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        if ": " not in line:
            continue
        
        try:
            offset_str, text = line.split(": ", 1)
            offset = int(offset_str, 16)
            text = text.strip()
            
            # Calculate original length
            end = rom_data.find(b"\xFF", offset)
            if end == -1:
                print(f"Error: Could not find end of string at {hex(offset)}")
                continue
            orig_len = end - offset + 1
            
            # Calculate new length (approximate, counting chars + special tokens)
            # Better: use the inject_translations encoding logic if possible, but for now manual check
            # We'll just count bytes roughly. 
            # Actually, let's just use the length of the text string as a lower bound? 
            # No, special tokens like {COLOR} are multiple bytes.
            # Let's assume 1 char = 1 byte for normal text.
            
            # Quick encoding
            encoded_len = 0
            j = 0
            while j < len(text):
                if text[j] == "{" and "}" in text[j:]:
                    end_tok = text.find("}", j)
                    token = text[j:end_tok+1]
                    # Assume tokens are 1 byte unless known otherwise? 
                    # Actually most tokens are 1 byte in charmap, but some control codes are sequences.
                    # {COLOR} is usually followed by a byte.
                    if token == "{COLOR}":
                        encoded_len += 2 # byte + arg
                        j = end_tok + 1
                        # The next char is the arg, usually mapped.
                        if j < len(text):
                             # The arg is part of the token sequence in the file?
                             # In the file it's {COLOR}É. É is the arg.
                             pass
                    elif token.startswith("{STR_VAR"):
                        encoded_len += 2 # FD XX
                        j = end_tok + 1
                    else:
                        encoded_len += 1
                        j = end_tok + 1
                elif text[j] == "\\":
                    encoded_len += 1 # \p, \n, \l are 1 byte
                    j += 2
                else:
                    encoded_len += 1
                    j += 1
            encoded_len += 1 # Terminator
            
            diff = encoded_len - orig_len
            has_ptr = offset in pointers
            
            if diff > 0 and not has_ptr:
                print(f"DANGER: Line {i+1} Offset {hex(offset)} overflows by {diff} bytes ({encoded_len} > {orig_len}) and HAS NO POINTER!")
                print(f"Text: {text[:20]}...")
            elif diff > 0:
                print(f"Info: Line {i+1} Offset {hex(offset)} overflows by {diff} bytes but has pointer.")
                
        except ValueError:
            pass

if __name__ == "__main__":
    main()
