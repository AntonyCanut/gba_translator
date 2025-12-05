#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

SOURCE = Path("extracted_text.txt")
TARGET = Path("extracted_text_fr.txt")

# Manuel : traductions déjà validées pour démarrer.
# Les clés sont les offsets (comme présents dans extracted_text.txt).
TRANSLATIONS = {
    "0x028780": "Le type de {B_ATK_NAME_WITH_PREFIX} devient\\nle même que celui de {B_DEF_NAME_WITH_PREFIX} !",
    "0x172482": "Je suis peut-être petite, mais je n'apprécierai pas\\nque tu me ménages !",
    "0x1724BF": "Oh, zut.\\nRien n'a marché.",
    "0x1724DC": "J'ai perdu une partie de mon argent de poche…",
    "0x1724F9": "Tu savais que les Pokémon évoluent ?",
    "0x17251B": "Oh !\\nJ'ai perdu !",
    "0x172FC3": "Seuls les dresseurs qui ont prouvé\\leur valeur au combat peuvent\\lpasser par ici.\\p...\\pTu n'es pas digne.",
    "0x1737AF": "{PLAYER} a reçu la CS01\\ndu CAPITAINE !",
    "0x1762D7": "{PLAYER} a reçu un LOKHLASS de\\nl'employé de SYLPHE SARL !",
    "0x176FBD": "{PLAYER} a reçu une MASTER BALL\\ndu PRÉSIDENT !",
    "0x177364": "Qui es-tu ?\\nQue fais-tu ici ?",
    "0x177391": "Ouah !",
    "0x177397": "Une statue avec un interrupteur ?\\nJamais entendu parler.",
    "0x1773C6": "Tu connais les secrets que cache\\nce manoir ?",
    "0x1773FD": "Je vais te le dire.",
    "0x177460": "Un interrupteur secret !\\pAppuyer dessus ?",
    "0x17747B": "Qui ne le ferait pas ?",
    "0x177489": "Pas tout de suite !",
    "0x177498": "Je ne trouve pas la Successeur Maxima !",
    "0x1774CB": "Oh non ! J'ai perdu !",
}


def main() -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    out_lines = []

    for line in lines:
        if ": " not in line:
            out_lines.append(line)
            continue
        offset, text = line.split(": ", 1)
        translated = TRANSLATIONS.get(offset.strip())
        out_lines.append(f"{offset}: {translated if translated is not None else text}")

    TARGET.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"Écriture terminée dans {TARGET} ({len(TRANSLATIONS)} traductions appliquées).")


if __name__ == "__main__":
    main()
