import struct
import os
import sys
import subprocess
from pathlib import Path

# Configuration
ROM_NAME = "test_rom.gba"
OUT_ROM_NAME = "test_rom_out.gba"
TEXT_FILE = "test_text.txt"
CHARMAP_FILE = "test_charmap.txt"

def create_test_files():
    # 1. Create a dummy ROM
    # Size 4KB
    rom_data = bytearray([0xFF] * 4096)
    
    # Text at 0x100: "Line1\nLine2" + 0xFF
    # \n = FE
    # Line1 = 4C 69 6E 65 31
    # Line2 = 4C 69 6E 65 32
    text_offset = 0x100
    # "Line1" (5) + FE + "Line2" (5) + FF
    original_text = b"Line1\xfeLine2\xff" 
    rom_data[text_offset : text_offset + len(original_text)] = original_text
    
    # Pointer 1 at 0x200 -> 0x100 (Start)
    ptr1_offset = 0x200
    ptr1_val = 0x08000000 + text_offset
    rom_data[ptr1_offset : ptr1_offset + 4] = struct.pack("<I", ptr1_val)
    
    # Pointer 2 at 0x204 -> 0x106 (Start of Line2, after \n)
    # 0x100 + 5 (Line1) + 1 (\n) = 0x106
    ptr2_offset = 0x204
    ptr2_val = 0x08000000 + text_offset + 6
    rom_data[ptr2_offset : ptr2_offset + 4] = struct.pack("<I", ptr2_val)
    
    with open(ROM_NAME, "wb") as f:
        f.write(rom_data)
        
    # 2. Create Charmap
    # We need to map characters and \n
    with open(CHARMAP_FILE, "w") as f:
        # Basic ASCII mapping for test
        # \n is handled by script logic (FE)
        content = ""
        for i in range(32, 127):
            char = chr(i)
            if char == "'":
                content += "'\\''=" + hex(i)[2:] + "\n"
            elif char == "=":
                content += "'='=" + hex(i)[2:] + "\n"
            else:
                content += f"'{char}'={hex(i)[2:]}\n"
        # Add \n mapping if needed for encoding?
        # The script handles \n -> FE automatically if not in charmap?
        # No, encode_text checks value_to_seq.get("\\n").
        # So we MUST add it to charmap.
        content += "'\\n'=FE\n"
        content += "'\\p'=FB\n"
        content += "'\\l'=FA\n"
        f.write(content)

    # 3. Create Text File
    # Replace with "LongLine1\nLine2"
    # "LongLine1" (9) + FE + "Line2" (5) + FF
    # Total 16 bytes. Original was 12. Relocation forced.
    with open(TEXT_FILE, "w") as f:
        f.write(f"{hex(text_offset)}: LongLine1\\nLine2\n")

def run_injection():
    cmd = [
        sys.executable, "inject_translations.py",
        "--rom", ROM_NAME,
        "--charmap", CHARMAP_FILE,
        "--text", TEXT_FILE,
        "--out", OUT_ROM_NAME,
        "--allow-append",
        "--ignore-sensitive"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    return result.returncode

def verify():
    with open(OUT_ROM_NAME, "rb") as f:
        data = f.read()
        
    # 1. Check Pointer 1 (Start)
    ptr1 = struct.unpack("<I", data[0x200:0x204])[0]
    new_offset = ptr1 - 0x08000000
    print(f"Pointer 1 (Start) is now: {hex(ptr1)} -> Offset {hex(new_offset)}")
    
    if new_offset == 0x100:
        print("FAIL: Text was not relocated!")
        return False
        
    # 2. Check Pointer 2 (Mid)
    # It should point to the new Line2.
    # New text: "LongLine1" (9) + FE + "Line2"
    # Offset of Line2 = new_offset + 9 + 1 = new_offset + 10
    ptr2 = struct.unpack("<I", data[0x204:0x208])[0]
    target2 = ptr2 - 0x08000000
    print(f"Pointer 2 (Mid) is now: {hex(ptr2)} -> Offset {hex(target2)}")
    
    expected_target2 = new_offset + 10
    if target2 == expected_target2:
        print(f"PASS: Pointer 2 correctly updated to {hex(target2)} (Smart Repoint)")
    else:
        print(f"FAIL: Pointer 2 is {hex(target2)}, expected {hex(expected_target2)}")
        return False
        
    # 3. Check Old Space
    # Since we successfully repointed, the old space SHOULD be freed (filled with FF),
    # unless we disabled reuse. Default is reuse=True.
    # Original text len 12.
    old_text = data[0x100:0x100+12]
    print(f"Old text area content: {old_text.hex()}")
    
    if old_text == b"\xff" * 12:
        print("PASS: Old text space was freed.")
    else:
        print("WARNING: Old text space NOT freed (Safety fallback triggered?)")
        # If safety triggered, then Pointer 2 should still be 0x106.
        if target2 == 0x106:
             print("...confirmed safety fallback (Smart Repoint failed).")
             return False

    return True

def create_unsafe_test_files():
    # Similar setup but translation will lack the anchor
    create_test_files()
    # Overwrite text file with something that lacks \n
    with open(TEXT_FILE, "w") as f:
        # "LongLine1XLine2" - No \n (FE)
        f.write(f"{hex(0x100)}: LongLine1XLine2\n")

def verify_unsafe():
    with open(OUT_ROM_NAME, "rb") as f:
        data = f.read()
        
    # 1. Check Pointer 1 (Start)
    ptr1 = struct.unpack("<I", data[0x200:0x204])[0]
    target1 = ptr1 - 0x08000000
    print(f"Pointer 1 (Start) is now: {hex(ptr1)} -> Offset {hex(target1)}")
    
    # Expectation: Pointer 1 should STILL point to 0x100 (Old location)
    if target1 == 0x100:
        print("PASS: Pointer 1 preserved (Unsafe relocation aborted)")
    else:
        print(f"FAIL: Pointer 1 moved to {hex(target1)} despite unsafe condition!")
        return False
        
    # 2. Check Pointer 2 (Mid)
    ptr2 = struct.unpack("<I", data[0x204:0x208])[0]
    target2 = ptr2 - 0x08000000
    print(f"Pointer 2 (Mid) is now: {hex(ptr2)} -> Offset {hex(target2)}")
    
    # Expectation: Pointer 2 should STILL point to 0x106 (Old location)
    if target2 == 0x106:
        print("PASS: Pointer 2 preserved")
    else:
        print(f"FAIL: Pointer 2 moved to {hex(target2)}")
        return False
        
    # 3. Check Old Space Content
    # Should be original "Line1\nLine2"
    old_text = data[0x100:0x100+12]
    print(f"Old text area content: {old_text.hex()}")
    if old_text.startswith(b"Line1\xfeLine2"):
        print("PASS: Old text preserved")
    else:
        print("FAIL: Old text corrupted/overwritten")
        return False
        
    return True

def main():
    try:
        print("--- Test 1: Safe Relocation (Smart Repoint) ---")
        create_test_files()
        if run_injection() != 0:
            print("Injection failed")
            return
        if not verify():
            print("TEST 1 FAILED")
            return
        print("TEST 1 PASSED\n")
        
        print("--- Test 2: Unsafe Relocation (Missing Anchor) ---")
        create_unsafe_test_files()
        if run_injection() != 0:
            # It might return non-zero if warnings? No, usually 0 unless error.
            # But we expect warnings.
            pass
            
        if verify_unsafe():
            print("TEST 2 PASSED\n")
        else:
            print("TEST 2 FAILED\n")

        print("--- Test 3: Punctuation Anchor (!) ---")
        create_punctuation_test_files()
        if run_injection() != 0:
            print("Injection failed")
            return
        if verify_punctuation():
            print("TEST 3 PASSED\n")
        else:
            print("TEST 3 FAILED\n")

        print("--- Test 4: Fewer Anchors (Fallback) ---")
        create_fallback_test_files()
        if run_injection() != 0:
            print("Injection failed")
            return
        if verify_fallback():
            print("TEST 4 PASSED\n")
        else:
            print("TEST 4 FAILED\n")

        print("--- Test 5: No Anchors (Proportional Fallback) ---")
        create_proportional_test_files()
        if run_injection() != 0:
            # Warnings expected
            pass
        if verify_proportional():
            print("TEST 5 PASSED")
        else:
            print("TEST 5 FAILED")
            
    finally:
        # Cleanup
        for f in [ROM_NAME, OUT_ROM_NAME, TEXT_FILE, CHARMAP_FILE]:
            if os.path.exists(f):
                os.remove(f)

def create_proportional_test_files():
    # 1. Create ROM with "AAAA!BBBB"
    # ! = AB
    rom_data = bytearray([0xFF] * 4096)
    text_offset = 0x100
    # "AAAA" (4) + ! + "BBBB" (4) + FF
    original_text = b"AAAA\xabBBBB\xff"
    rom_data[text_offset : text_offset + len(original_text)] = original_text
    
    # Pointer 1: Start (0x100)
    ptr1_offset = 0x200
    ptr1_val = 0x08000000 + text_offset
    rom_data[ptr1_offset : ptr1_offset + 4] = struct.pack("<I", ptr1_val)
    
    # Pointer 2: Pointing to "BBBB" (After !)
    # 0x100 + 4 + 1 = 0x105
    ptr2_offset = 0x204
    ptr2_val = 0x08000000 + text_offset + 5
    rom_data[ptr2_offset : ptr2_offset + 4] = struct.pack("<I", ptr2_val)
    
    with open(ROM_NAME, "wb") as f:
        f.write(rom_data)
        
    # 2. Charmap
    with open(CHARMAP_FILE, "w") as f:
        content = ""
        for i in range(32, 127):
            char = chr(i)
            if char == '!': continue
            content += f"'{char}'={hex(i)[2:]}\n"
        content += "'!'=AB\n"
        f.write(content)
        
    # 3. Text File
    # "XXXXXXXXXX" (No anchors, length 10)
    # Original length: 4+1+4 = 9 (excluding FF)
    # Original pointer at 5 (after 4 chars + 1 anchor) -> 5/9 = 55%
    # New length: 10
    # Expected pointer: 10 * (5/9) = 5.5 -> 5
    with open(TEXT_FILE, "w") as f:
        f.write(f"{hex(text_offset)}: XXXXXXXXXX\n")

def verify_proportional():
    with open(OUT_ROM_NAME, "rb") as f:
        data = f.read()
        
    # Check Pointer 2
    ptr2 = struct.unpack("<I", data[0x204:0x208])[0]
    target2 = ptr2 - 0x08000000
    print(f"Pointer 2 (Mid) is now: {hex(ptr2)} -> Offset {hex(target2)}")
    
    # Where is the new text?
    ptr1 = struct.unpack("<I", data[0x200:0x204])[0]
    target1 = ptr1 - 0x08000000
    print(f"Pointer 1 (Start) is now: {hex(ptr1)} -> Offset {hex(target1)}")
    
    # Expected: target1 + 5
    expected_target2 = target1 + 5
    
    if target2 == expected_target2:
        print(f"PASS: Pointer 2 updated proportionally to {hex(target2)}")
        return True
    else:
        print(f"FAIL: Pointer 2 is {hex(target2)}, expected {hex(expected_target2)}")
        return False

def create_fallback_test_files():
    # 1. Create ROM with "Part1!Part2!Part3"
    # ! = AB
    rom_data = bytearray([0xFF] * 4096)
    text_offset = 0x100
    # "Part1" (5) + ! + "Part2" (5) + ! + "Part3" (5) + FF
    original_text = b"Part1\xabPart2\xabPart3\xff"
    rom_data[text_offset : text_offset + len(original_text)] = original_text
    
    # Pointer 1: Start (0x100)
    ptr1_offset = 0x200
    ptr1_val = 0x08000000 + text_offset
    rom_data[ptr1_offset : ptr1_offset + 4] = struct.pack("<I", ptr1_val)
    
    # Pointer 2: Pointing to "Part3" (After 2nd !)
    # 0x100 + 5+1 + 5+1 = 0x10C
    ptr2_offset = 0x204
    ptr2_val = 0x08000000 + text_offset + 12
    rom_data[ptr2_offset : ptr2_offset + 4] = struct.pack("<I", ptr2_val)
    
    with open(ROM_NAME, "wb") as f:
        f.write(rom_data)
        
    # 2. Charmap
    with open(CHARMAP_FILE, "w") as f:
        content = ""
        for i in range(32, 127):
            char = chr(i)
            if char == '!': continue
            content += f"'{char}'={hex(i)[2:]}\n"
        content += "'!'=AB\n"
        f.write(content)
        
    # 3. Text File
    # "Partie1!Partie2et3" (Only 1 !)
    # "Partie1" (7) + ! + "Partie2et3" (10)
    with open(TEXT_FILE, "w") as f:
        f.write(f"{hex(text_offset)}: Partie1!Partie2et3\n")

def verify_fallback():
    with open(OUT_ROM_NAME, "rb") as f:
        data = f.read()
        
    # Pointer 2 pointed to "Part3" (After 2nd !).
    # Translation has only 1 !.
    # Fallback logic should point to "After 1st !" (the last one found).
    
    # Check Pointer 2
    ptr2 = struct.unpack("<I", data[0x204:0x208])[0]
    target2 = ptr2 - 0x08000000
    print(f"Pointer 2 (Mid) is now: {hex(ptr2)} -> Offset {hex(target2)}")
    
    # Where is the new text?
    ptr1 = struct.unpack("<I", data[0x200:0x204])[0]
    target1 = ptr1 - 0x08000000
    print(f"Pointer 1 (Start) is now: {hex(ptr1)} -> Offset {hex(target1)}")
    
    # "Partie1" is 7 chars. ! is 1 char.
    # So "Partie2et3" starts at target1 + 7 + 1 = target1 + 8.
    expected_target2 = target1 + 8
    
    if target2 == expected_target2:
        print(f"PASS: Pointer 2 correctly updated to {hex(target2)} (Fallback to last anchor)")
        return True
    else:
        print(f"FAIL: Pointer 2 is {hex(target2)}, expected {hex(expected_target2)}")
        return False

def create_punctuation_test_files():
    # 1. Create ROM with "Hello!World"
    # ! = AB
    rom_data = bytearray([0xFF] * 4096)
    text_offset = 0x100
    # "Hello" (5) + ! (AB) + "World" (5) + FF
    # 48 65 6C 6C 6F AB 57 6F 72 6C 64 FF
    original_text = b"Hello\xabWorld\xff"
    rom_data[text_offset : text_offset + len(original_text)] = original_text
    
    # Pointer 1: Start (0x100)
    ptr1_offset = 0x200
    ptr1_val = 0x08000000 + text_offset
    rom_data[ptr1_offset : ptr1_offset + 4] = struct.pack("<I", ptr1_val)
    
    # Pointer 2: Mid (after !) -> "World"
    # 0x100 + 5 + 1 = 0x106
    ptr2_offset = 0x204
    ptr2_val = 0x08000000 + text_offset + 6
    rom_data[ptr2_offset : ptr2_offset + 4] = struct.pack("<I", ptr2_val)
    
    with open(ROM_NAME, "wb") as f:
        f.write(rom_data)
        
    # 2. Charmap
    with open(CHARMAP_FILE, "w") as f:
        content = ""
        for i in range(32, 127):
            char = chr(i)
            if char == '!': continue
            content += f"'{char}'={hex(i)[2:]}\n"
        content += "'!'=AB\n"
        f.write(content)
        
    # 3. Text File
    # "Bonjour!Monde" (Longer)
    # "Bonjour" (7) + ! + "Monde" (5)
    with open(TEXT_FILE, "w") as f:
        f.write(f"{hex(text_offset)}: Bonjour!Monde\n")

def verify_punctuation():
    with open(OUT_ROM_NAME, "rb") as f:
        data = f.read()
        
    # Pointer 2 should point to "Monde"
    # New text starts at dest_offset (likely 0x100 + len(original) + gap? or appended?)
    # Since we use --allow-append, it might be appended.
    # But wait, we reuse old space if it fits? No, "Bonjour!Monde" (13) > "Hello!World" (11).
    # So it relocates.
    
    # Check Pointer 2
    ptr2 = struct.unpack("<I", data[0x204:0x208])[0]
    target2 = ptr2 - 0x08000000
    print(f"Pointer 2 (Mid) is now: {hex(ptr2)} -> Offset {hex(target2)}")
    
    # Where is the new text?
    # Pointer 1 should tell us.
    ptr1 = struct.unpack("<I", data[0x200:0x204])[0]
    target1 = ptr1 - 0x08000000
    print(f"Pointer 1 (Start) is now: {hex(ptr1)} -> Offset {hex(target1)}")
    
    # "Bonjour" is 7 chars. ! is 1 char.
    # So "Monde" starts at target1 + 7 + 1 = target1 + 8.
    expected_target2 = target1 + 8
    
    if target2 == expected_target2:
        print(f"PASS: Pointer 2 correctly updated to {hex(target2)} (after !)")
        return True
    else:
        print(f"FAIL: Pointer 2 is {hex(target2)}, expected {hex(expected_target2)}")
        return False

if __name__ == "__main__":
    main()
