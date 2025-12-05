#!/usr/bin/env python3
from pathlib import Path
import argparse


def main():
    parser = argparse.ArgumentParser(description="Découpe un fichier texte en morceaux.")
    parser.add_argument("--input", required=True, help="Fichier source à découper")
    parser.add_argument("--out-dir", required=True, help="Dossier de sortie pour les chunks")
    parser.add_argument("--size", type=int, default=250, help="Nombre de lignes par chunk")
    args = parser.parse_args()

    src = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = src.read_text(encoding="utf-8").splitlines()
    for idx in range(0, len(lines), args.size):
        chunk = lines[idx : idx + args.size]
        fname = out_dir / f"chunk_{idx // args.size + 1:02d}.txt"
        fname.write_text("\n".join(chunk), encoding="utf-8")


if __name__ == "__main__":
    main()
