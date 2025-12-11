from inject_translations import find_target_by_anchor

def test():
    # Data with one '!' (0xAB) at index 2 (byte 3)
    # 00 00 AB 00
    data = b"\x00\x00\xAB\x00"
    
    # Case 1: Find 1st '!' (index 0)
    # Should return 3
    pos = find_target_by_anchor(data, 0xAB, 0)
    print(f"Find 1st !: {pos} (Expected 3)")
    
    # Case 2: Find 2nd '!' (index 1) - Missing
    # Should fallback to 3 (last found)
    pos = find_target_by_anchor(data, 0xAB, 1)
    print(f"Find 2nd !: {pos} (Expected 3 - Fallback)")
    
    # Case 3: Find '?' (0xAC) - Completely missing
    # Should return None
    pos = find_target_by_anchor(data, 0xAC, 0)
    print(f"Find ?: {pos} (Expected None)")

if __name__ == "__main__":
    test()
