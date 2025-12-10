#!/usr/bin/env python3
"""
Merge combined_fr.txt over old_combined_fr.txt by offset.
Offsets present in combined_fr.txt override the ones in old_combined_fr.txt.
Result is written to merge_combined_fr.txt in the project root.
"""

from pathlib import Path


def load_map(path: Path) -> dict[str, str]:
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        offset, text = line.split(":", 1)
        data[offset.strip()] = text.lstrip()
    return data


def main():
    root = Path(".")
    old_path = root / "old_combined_fr.txt"
    new_path = root / "combined_fr.txt"
    out_path = root / "merge_combined_fr.txt"

    old_map = load_map(old_path)
    new_map = load_map(new_path)

    # Apply overrides from combined_fr.txt
    for off, txt in new_map.items():
        old_map[off] = txt

    # Preserve original order of old_combined_fr.txt; append any new offsets
    merged_lines = []
    seen = set()
    for line in old_path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            merged_lines.append(line)
            continue
        off = line.split(":", 1)[0].strip()
        merged_lines.append(f"{off}: {old_map.get(off, '').strip()}")
        seen.add(off)

    # Append offsets only in combined_fr that were not in old
    for off, txt in new_map.items():
        if off not in seen:
            merged_lines.append(f"{off}: {txt}")

    out_path.write_text("\n".join(merged_lines) + "\n", encoding="utf-8")
    print(f"Merged file written to {out_path}")


if __name__ == "__main__":
    main()
