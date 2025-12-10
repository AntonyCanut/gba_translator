#!/usr/bin/env python3
"""
Inject translations from merge_combined_fr.txt into a base file (extracted_text_fr.txt)
by matching offsets. Offsets present in the override replace the base text; offsets
absent from the base are appended at the end.
"""

from pathlib import Path
import argparse


def load_map(path: Path) -> dict[str, str]:
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        offset, text = line.split(":", 1)
        data[offset.strip()] = text.lstrip()
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Merge override translations into a base text file by offset."
    )
    parser.add_argument(
        "--base",
        default="backup/extracted_text_fr.txt",
        help="Base file providing offset order (default: backup/extracted_text_fr.txt).",
    )
    parser.add_argument(
        "--override",
        default="merge_combined_fr.txt",
        help="File containing translations to inject (default: merge_combined_fr.txt).",
    )
    parser.add_argument(
        "--out",
        default="super_merge_combined_fr.txt",
        help="Output path (default: super_merge_combined_fr.txt).",
    )
    args = parser.parse_args()

    base_path = Path(args.base)
    override_path = Path(args.override)
    out_path = Path(args.out)

    override_map = load_map(override_path)

    merged_lines = []
    seen_offsets = set()

    base_lines = base_path.read_text(encoding="utf-8").splitlines()
    for line in base_lines:
        if ":" not in line:
            merged_lines.append(line)
            continue
        offset, text = line.split(":", 1)
        off = offset.strip()
        seen_offsets.add(off)
        if off in override_map:
            merged_lines.append(f"{off}: {override_map[off]}")
        else:
            merged_lines.append(line)

    # Append offsets present only in the override file (preserve override order).
    for line in override_path.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        off = line.split(":", 1)[0].strip()
        if off not in seen_offsets:
            merged_lines.append(f"{off}: {override_map[off]}")
            seen_offsets.add(off)

    out_path.write_text("\n".join(merged_lines) + "\n", encoding="utf-8")
    print(f"Wrote merged file to {out_path}")


if __name__ == "__main__":
    main()
