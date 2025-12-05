#!/usr/bin/env python3
"""
Post-traitement des textes traduits :
- ajoute des sauts de ligne \\n pour que chaque segment fasse au plus 36 caractères
  (entre deux marqueurs \\n/\\p/\\l ou la fin du texte) en coupant avant le mot qui dépasse,
  la ponctuation faisant partie du mot.
- remplace "Gim Leader(s)" par "Champion(s) d'Arêne" et "Gim" par "Arêne".
- force la traduction des noms de Pokémon en français, même juste après un marqueur.

Le fichier traité est extracted_text_fr.txt (écrasé).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Callable, Dict, List

import requests

TEXT_FILE = Path("extracted_text_fr.txt")
MARKERS = {"\\n", "\\p", "\\l"}
MAX_COLS = 36
ALNUM = "A-Za-zÀ-ÿ0-9"


def split_tokens(text: str) -> List[str]:
    """Sépare les marqueurs \\n/\\p/\\l du reste."""
    tokens: List[str] = []
    buf = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "\\" and i + 1 < n and text[i + 1] in {"n", "p", "l"}:
            if buf:
                tokens.append("".join(buf))
                buf.clear()
            tokens.append(text[i : i + 2])
            i += 2
            continue
        buf.append(text[i])
        i += 1
    if buf:
        tokens.append("".join(buf))
    return tokens


def build_pokemon_sub() -> Callable[[str], str]:
    """Construit une fonction qui remplace les noms EN -> FR (insensible à la casse)."""
    base = "https://raw.githubusercontent.com/veekun/pokedex/master/pokedex/data/csv"
    names_csv = requests.get(f"{base}/pokemon_species_names.csv", timeout=60).text

    english: Dict[int, str] = {}
    french: Dict[int, str] = {}
    for row in csv.DictReader(names_csv.splitlines()):
        try:
            sid = int(row["pokemon_species_id"])
            lang = int(row["local_language_id"])
        except Exception:
            continue
        name = row.get("name", "")
        if lang == 9:
            english[sid] = name
        elif lang == 5:
            french[sid] = name

    eng_to_fr: Dict[str, str] = {}
    for sid, en in english.items():
        fr = french.get(sid)
        if fr:
            eng_to_fr[en] = fr

    # Corrections / variantes
    eng_to_fr.update(
        {
            "Mr. Mime": "M. Mime",
            "Mime Jr.": "Mime Jr.",
            "Type: Null": "Type:0",
            "Farfetch'd": "Canarticho",
            "Sirfetch'd": "Palarticho",
        }
    )

    lower_map = {k.lower(): v for k, v in eng_to_fr.items()}
    names = sorted(lower_map.keys(), key=len, reverse=True)
    pattern = re.compile(
        rf"(?<![{ALNUM}])(" + "|".join(re.escape(n) for n in names) + rf")(?![{ALNUM}])",
        flags=re.IGNORECASE,
    )

    def repl(match: re.Match[str]) -> str:
        src = match.group(1)
        fr = lower_map.get(src.lower())
        if not fr:
            return src
        if src.isupper():
            return fr.upper()
        if src[0].isupper() and src[1:].islower():
            return fr
        return fr

    def sub(text: str) -> str:
        return pattern.sub(repl, text)

    return sub


def case_replace(match: re.Match[str], replacement: str) -> str:
    src = match.group(0)
    if src.isupper():
        return replacement.upper()
    if src[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def fix_terms(text: str, pokemon_sub: Callable[[str], str]) -> str:
    text = re.sub(
        r"\bGim Leaders\b",
        lambda m: case_replace(m, "Champions d'Arêne"),
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bGim Leader\b",
        lambda m: case_replace(m, "Champion d'Arêne"),
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bGim\b",
        lambda m: case_replace(m, "Arêne"),
        text,
        flags=re.IGNORECASE,
    )
    text = pokemon_sub(text)
    return text


def wrap_segment(segment: str, cur_len: int) -> tuple[List[str], int]:
    """Retourne des morceaux (mots/espaces/\\n ajoutés) et la longueur courante."""
    parts = re.findall(r"\S+|\s+", segment)
    out: List[str] = []
    pending_space = ""
    for part in parts:
        if part.isspace():
            pending_space += part
            continue
        word = part
        add_space = len(pending_space) if cur_len > 0 else 0
        if cur_len + add_space + len(word) > MAX_COLS and cur_len > 0:
            out.append("\\n")
            cur_len = 0
            pending_space = ""
            add_space = 0
        if cur_len > 0 and pending_space:
            out.append(pending_space)
            cur_len += len(pending_space)
        pending_space = ""
        out.append(word)
        cur_len += len(word)
    return out, cur_len


def process_text(text: str, pokemon_sub: Callable[[str], str]) -> str:
    # Supprime tous les anciens sauts de ligne \n et remplace par un espace pour éviter de coller les mots
    text = text.replace("\\n", " ")
    # Normalise les espaces
    text = " ".join(text.split())
    tokens = split_tokens(text)
    out: List[str] = []
    cur_len = 0
    for tok in tokens:
        if tok in MARKERS:
            out.append(tok)
            cur_len = 0
            continue
        fixed = fix_terms(tok, pokemon_sub)
        wrapped_parts, cur_len = wrap_segment(fixed, cur_len)
        out.extend(wrapped_parts)
    return "".join(out)


def main() -> None:
    pokemon_sub = build_pokemon_sub()
    lines = TEXT_FILE.read_text(encoding="utf-8").splitlines()
    out_lines: List[str] = []
    for line in lines:
        if ": " not in line:
            out_lines.append(line)
            continue
        off, txt = line.split(": ", 1)
        new_txt = process_text(txt, pokemon_sub)
        out_lines.append(f"{off}: {new_txt}")
    TEXT_FILE.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"{TEXT_FILE} mis à jour ({len(out_lines)} lignes).")


if __name__ == "__main__":
    main()
