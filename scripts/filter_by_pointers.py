#!/usr/bin/env python3
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Filter a text file to keep only lines pointed to by the ROM.")
    parser.add_argument("--input", type=Path, required=True, help="Input text file (offset: text)")
    parser.add_argument("--rom", type=Path, required=True, help="ROM file (.gba)")
    parser.add_argument("--output", type=Path, required=True, help="Output filtered text file")
    args = parser.parse_args()

    # Pas de filtrage : on recopie simplement l'entrée vers la sortie.
    if not args.input.exists():
        print(f"Error: {args.input} not found.")
        return

    content = args.input.read_text(encoding="utf-8")
    args.output.write_text(content, encoding="utf-8")
    print(f"No filtering applied. Copied {args.input} to {args.output}")

if __name__ == "__main__":
    main()
