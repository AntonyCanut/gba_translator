#!/usr/bin/env python3
"""Écrire en place les titres de mission FR sans décaler l'injection générale.

Le titre ``The Food Thief`` est plus court que ``Voleur de vivres``. L'ajouter
à l'injecteur générique décalait toutes les chaînes relocalisées suivantes et
invalidait notamment les pointeurs en mémoire du replay de capture. Rechercher
et repointer ses références élargit inutilement le diff et a également fait
échouer ce replay lors du diagnostic.

Le correctif écrit donc le titre à son adresse d'origine, sans toucher aucun
pointeur. Ses deux octets supplémentaires chevauchent le début de la description
voisine à ``0x1FA4E1F`` ; cette description appartient au patch
``mission_descriptions.py``, exécuté juste après et chargé de la relocaliser
intégralement. La traduction reste dans ``combined_fr.txt`` et son offset est
exclu des passes générique et inline.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from src.core.text_codec import TextEncoder  # noqa: E402

DEFAULT_COMBINED = REPO_ROOT / "languages/fr/combined_fr.txt"

TARGETS: tuple[int, ...] = (0x1FA4E10,)
RELOCATED_NEIGHBOR_OFFSET = 0x1FA4E1F
_OFFSET_LINE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def load_combined(path: Path) -> dict[int, str]:
    """Lire ``combined_fr.txt`` avec la règle « dernière entrée gagnante »."""
    mapping: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _OFFSET_LINE.match(line)
        if match:
            mapping[int(match.group(1), 16)] = match.group(2)
    return mapping


def apply(
    rom: bytearray,
    combined: dict[int, str],
) -> dict[str, int]:
    """Écrire chaque titre à son offset source, sans modifier de pointeur."""
    stats = {"targets": 0, "failed": 0, "skipped": 0}

    for offset in TARGETS:
        text = combined.get(offset)
        if not text:
            stats["failed"] += 1
            continue

        encoded = TextEncoder.encode(text, "pokemon")
        if offset + len(encoded) > len(rom):
            stats["failed"] += 1
            continue
        if bytes(rom[offset : offset + len(encoded)]) == encoded:
            stats["skipped"] += 1
            continue

        rom[offset : offset + len(encoded)] = encoded
        stats["targets"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--combined", type=Path, default=DEFAULT_COMBINED)
    args = parser.parse_args()

    rom = bytearray(args.rom.read_bytes())
    combined = load_combined(args.combined)

    stats = apply(rom, combined)
    if stats["failed"]:
        print(f"✗ Titres de mission : {stats['failed']} cible(s) non appliquée(s)")
        return 1

    args.rom.write_bytes(rom)
    print(
        "✓ Titres de mission : "
        f"{stats['targets']} écrit(s) en place, "
        f"{stats['skipped']} déjà correct(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
