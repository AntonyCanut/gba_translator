#!/usr/bin/env python3
from pathlib import Path
import argparse


def main():
    parser = argparse.ArgumentParser(description="Recolle des chunks en un seul fichier.")
    parser.add_argument("--dir", required=True, help="Dossier contenant les chunks chunk_XX.txt")
    parser.add_argument("--output", required=True, help="Fichier de sortie combiné")
    args = parser.parse_args()

    src_dir = Path(args.dir)
    out = Path(args.output)
    chunks = sorted(src_dir.glob("chunk_*.txt"))
    if not chunks:
        raise SystemExit(f"Aucun chunk trouvé dans {src_dir}")

    data = [f.read_text(encoding="utf-8").rstrip("\n") for f in chunks]
    out.write_text("\n".join(data), encoding="utf-8")


if __name__ == "__main__":
    main()
