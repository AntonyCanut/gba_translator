from pathlib import Path
import sys

# Copy-paste load_charmap from inject_translations.py to ensure identical behavior
def load_charmap(path: Path):
    mapping = {}
    if not path.exists():
        print(f"File not found: {path}")
        return mapping
        
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("@", 1)[0].strip()
        if not line or "=" not in line:
            continue
        left, right = [part.strip() for part in line.rsplit("=", 1)]
        seq = tuple(int(h, 16) for h in right.split())
        if left.startswith("'") and left.endswith("'"):
            val = left[1:-1]
        else:
            val = "{" + left + "}"
        
        # Special handling for \n, \p, \l if they are in the file as such?
        # The file format usually doesn't have \n.
        # Wait, if the file has:
        # \n = FE
        # Then left is "\n".
        # But the script says:
        # if left.startswith("'")... val = left[1:-1]
        # else val = "{" + left + "}"
        
        # So if the file has:
        # \n = FE
        # val becomes "{\n}" ??
        # That doesn't match what encode_text expects ("\n").
        
        # Let's see what the file actually has.
        if val not in mapping:
            mapping[val] = seq
            
    return mapping

# Actually, let's just inspect the file directly for the relevant bytes.
# We suspect FE, FA, FB.
def find_keys_for_values(path: Path):
    target_values = {
        (0xFE,): "FE",
        (0xFA,): "FA",
        (0xFB,): "FB",
        (0xFD,): "FD",
        (0xFF,): "FF"
    }
    
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("@", 1)[0].strip()
        if not line or "=" not in line:
            continue
        left, right = [part.strip() for part in line.rsplit("=", 1)]
        try:
            seq = tuple(int(h, 16) for h in right.split())
        except:
            continue
            
        if seq in target_values:
            print(f"Found {target_values[seq]}: {left} -> {seq}")

if __name__ == "__main__":
    find_keys_for_values(Path("../charmap_firered.txt"))
