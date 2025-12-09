#!/usr/bin/env python3
from pathlib import Path

def main():
    fr_current = Path("fr_chunks/chunk_54.txt").read_text().splitlines()
    fr_backup = Path("fr_chunks/chunk_54.txt.bak").read_text().splitlines()
    en_origin = Path("origin_chuncks/chunk_54.txt").read_text().splitlines()
    
    current_dict = {}
    for line in fr_current:
        if ": " in line:
            off, txt = line.split(": ", 1)
            current_dict[off] = txt.strip()
            
    backup_dict = {}
    for line in fr_backup:
        if ": " in line:
            off, txt = line.split(": ", 1)
            backup_dict[off] = txt.strip()
            
    origin_dict = {}
    for line in en_origin:
        if ": " in line:
            off, txt = line.split(": ", 1)
            origin_dict[off] = txt.strip()
            
    print(f"{'Offset':<12} | {'Len Diff':<8} | {'French (Backup)'}")
    print("-" * 80)
    
    count = 0
    for off, en_txt in origin_dict.items():
        curr_txt = current_dict.get(off)
        bak_txt = backup_dict.get(off)
        
        # If current matches English AND backup is different (meaning we have a translation pending)
        if curr_txt == en_txt and bak_txt != en_txt:
            # Calculate rough length diff (just char count for now, close enough for estimation)
            diff = len(bak_txt) - len(en_txt)
            print(f"{off:<12} | {diff:<8} | {bak_txt}")
            count += 1
            
    print(f"\nTotal remaining: {count}")

if __name__ == "__main__":
    main()
