import sys

def inspect(rom_path, offsets):
    with open(rom_path, "rb") as f:
        data = f.read()
        
    for off in offsets:
        start = max(0, off - 10)
        end = min(len(data), off + 10)
        chunk = data[start:end]
        
        print(f"--- Offset {hex(off)} ---")
        print(f"Context: {chunk.hex(' ')}")
        print(f"Byte at {hex(off)}: {hex(data[off])}")
        print(f"Byte before ({hex(off-1)}): {hex(data[off-1])}")
        
        # Try to decode around it
        try:
            # Simple ascii decode for visibility
            print(f"ASCII: {chunk.decode('ascii', errors='replace')}")
        except:
            pass

if __name__ == "__main__":
    # Offsets from new log:
    # Run 0x7fa608: Pointeur interne à 0x7fa63e
    # Run 0x419c0b: Pointeur interne à 0x419c1c
    # Run 0x1eff20e: Pointeur interne à 0x1eff254
    # Run 0x966c1a: Pointeur interne à 0x966c60
    offsets = [0x7fa63e, 0x419c1c, 0x1eff254, 0x966c60]
    inspect("../totranslate.gba", offsets)
