#!/usr/bin/env python3
"""
Identifie les lignes sensibles (données/commandes) dans extracted_text.txt,
les remplace dans extracted_text_fr.txt par la version originale anglaise
et enregistre la liste des numéros de lignes.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

TEXT_EN = Path("extracted_text.txt")
TEXT_FR = Path("extracted_text_fr.txt")
SENSITIVE_LIST = Path("sensitive_lines.txt")

# Lignes à forcer comme sensibles (contiguïté de tables critiques, ex: écran de nom)
EXTRA_LINES = set(range(620, 664))

# Caractères supplémentaires autorisés hors latin de base
ALLOWED_EXTRA = {
    0x2019,  # ’
    0x2018,  # ‘
    0x201C,  # “
    0x201D,  # ”
    0x2026,  # …
    0x00B7,  # ·
    0x2640,  # ♀
    0x2642,  # ♂
    0x00B0,  # °
    0x00A3,  # £
    0x00A5,  # ¥
    0x00A9,  # ©
    0x00AE,  # ®
    0x2014,  # —
    0x2013,  # –
}


def is_sensitive(text: str) -> bool:
    """Détecte les lignes contenant des caractères hors plage latine (Katakana, CJK, etc.)."""
    for ch in text:
        # Autorise les marqueurs d'échappement
        if ch == "\\":
            continue
        # Ponctuation et espaces courants
        if ch.isspace() or ch in "!?,.;:'\"-_/()[]%+&*=<>@#$|^~{}":
            continue
        o = ord(ch)
        # Latin étendu
        if o <= 0x024F or o in ALLOWED_EXTRA:
            continue
        # Katakana / Hiragana / CJK / autres caractères hors plage
        return True
    return False


def main() -> None:
    en_lines = TEXT_EN.read_text(encoding="utf-8").splitlines()
    fr_lines = TEXT_FR.read_text(encoding="utf-8").splitlines()
    if len(en_lines) != len(fr_lines):
        raise SystemExit("Les fichiers EN et FR n'ont pas le même nombre de lignes.")

    sensitive: List[int] = []
    for idx, line in enumerate(en_lines, 1):
        if ": " not in line:
            continue
        txt = line.split(": ", 1)[1]
        if is_sensitive(txt):
            sensitive.append(idx)

    # Ajout des lignes marquées manuellement
    sensitive = sorted(set(sensitive).union(EXTRA_LINES))

    # Écrire la liste des numéros de lignes
    SENSITIVE_LIST.write_text("\n".join(str(i) for i in sensitive), encoding="utf-8")

    # Remplacer dans la version FR
    for i in sensitive:
        fr_lines[i - 1] = en_lines[i - 1]

    TEXT_FR.write_text("\n".join(fr_lines), encoding="utf-8")
    print(f"Lignes sensibles détectées : {len(sensitive)}")
    print(f"Liste enregistrée dans {SENSITIVE_LIST}")
    print(f"{TEXT_FR} mis à jour avec les lignes originales EN pour ces entrées.")


if __name__ == "__main__":
    main()
