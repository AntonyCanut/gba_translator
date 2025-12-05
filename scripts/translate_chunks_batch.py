#!/usr/bin/env python3
"""
Traduction par lots des fichiers fr_chunks/chunk_XX.txt vers le français.
Conserve les marqueurs de mise en forme (\n, \p, \l, {VARS}) et remplace
les noms de Pokémon par leurs noms officiels en français.

Usage basique :
    python translate_chunks_batch.py

Options :
    --only 02 03    # traduirait uniquement chunk_02 et chunk_03
    --skip 01 28    # ignorerait ces chunks (chunk_01 déjà traduit à la main)
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, Iterable, List

import requests
from deep_translator import GoogleTranslator

CHUNKS_DIR = Path("fr_chunks")
ORIG_TEXT = Path("extracted_text_fr.txt")
PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")


def norm_name(text: str) -> str:
    return (
        text.lower()
        .replace("♀", "-f")
        .replace("♂", "-m")
        .replace("’", "'")
        .replace(".", "")
        .replace(" ", "-")
        .replace("\u2640", "-f")
        .replace("\u2642", "-m")
    )


def build_name_lookup() -> Dict[str, str]:
    """Map English identifier -> French official name (normalized keys)."""
    base = "https://raw.githubusercontent.com/veekun/pokedex/master/pokedex/data/csv"
    species_csv = requests.get(f"{base}/pokemon_species.csv", timeout=60).text
    names_csv = requests.get(f"{base}/pokemon_species_names.csv", timeout=60).text

    id_to_identifier: Dict[int, str] = {}
    for row in csv.DictReader(species_csv.splitlines()):
        try:
            sid = int(row["id"])
        except Exception:
            continue
        id_to_identifier[sid] = row["identifier"]

    lookup: Dict[str, str] = {}
    for row in csv.DictReader(names_csv.splitlines()):
        try:
            sid = int(row["pokemon_species_id"])
            lang = int(row["local_language_id"])
        except Exception:
            continue
        if lang != 5:  # 5 = français
            continue
        ident = id_to_identifier.get(sid)
        if ident:
            lookup[norm_name(ident)] = row["name"]

    # Corrections manuelles pour certaines formes
    lookup.update(
        {
            norm_name("mr-mime"): "M. Mime",
            norm_name("mime-jr"): "Mime Jr.",
            norm_name("type-null"): "Type:0",
            norm_name("jangmo-o"): "Bébécaille",
            norm_name("hakamo-o"): "Écaïd",
            norm_name("kommo-o"): "Ékaïser",
            norm_name("tapu-koko"): "Tokorico",
            norm_name("tapu-lele"): "Tokopiyon",
            norm_name("tapu-bulu"): "Tokotoro",
            norm_name("tapu-fini"): "Tokopisco",
        }
    )
    return lookup


def load_original_offsets() -> Dict[str, str]:
    """Offset -> texte original (utile pour repérer la liste des Pokémon)."""
    mapping: Dict[str, str] = {}
    for line in ORIG_TEXT.read_text(encoding="utf-8").splitlines():
        if ": " in line:
            off, txt = line.split(": ", 1)
            mapping[off] = txt
    return mapping


def protect(text: str):
    """Protège les marqueurs pour éviter qu'ils soient traduits."""
    placeholders = PLACEHOLDER_RE.findall(text)
    mapping = {f"__PH{i}__": p for i, p in enumerate(placeholders)}
    for k, v in mapping.items():
        text = text.replace(v, k)
    text = text.replace("\\n", "__NL__").replace("\\p", "__PP__").replace("\\l", "__LL__")
    return text, mapping


def restore(text: str, mapping: Dict[str, str]) -> str:
    text = text.replace("__NL__", "\\n").replace("__PP__", "\\p").replace("__LL__", "\\l")
    for k, v in mapping.items():
        text = text.replace(k, v)
    # Pas de vrais sauts de ligne dans le fichier : on aplati
    text = text.replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())
    return text


def translate_batch(translator: GoogleTranslator, texts: List[str]) -> List[str]:
    # Preprocess: split into two lists so we can skip overlong strings
    prepared: List[tuple[str, Dict[str, str]]] = []
    overlong_out: Dict[int, str] = {}
    for idx, t in enumerate(texts):
        p, m = protect(t)
        if len(p) > 4800:
            overlong_out[idx] = restore(p, m)
        else:
            prepared.append((p, m))

    # Translate the prepared subset
    translated_block: List[str] = []
    maps_block: List[Dict[str, str]] = []
    for p, m in prepared:
        translated_block.append(p)
        maps_block.append(m)

    results: List[str] = []
    if translated_block:
        try:
            tr_list = translator.translate_batch(translated_block)
        except Exception:
            tr_list = [translator.translate(p) for p in translated_block]
        if isinstance(tr_list, str):
            tr_list = [tr_list]
        restored = [restore(tr, m) for tr, m in zip(tr_list, maps_block)]
        results = restored

    # Merge back in original order
    out: List[str] = []
    translated_iter = iter(results)
    for idx in range(len(texts)):
        if idx in overlong_out:
            out.append(overlong_out[idx])
        else:
            out.append(next(translated_iter))
    return out


def translate_chunks(chunks: Iterable[Path], skip_offsets_name_map: Dict[str, str], name_lookup: Dict[str, str]) -> None:
    translator = GoogleTranslator(source="auto", target="fr")
    for chunk in chunks:
        lines = chunk.read_text(encoding="utf-8").splitlines()
        out_lines: List[str] = []
        batch_size = 50
        for i in range(0, len(lines), batch_size):
            batch = lines[i : i + batch_size]
            texts = [line.split(": ", 1)[1] if ": " in line else line for line in batch]
            translated = translate_batch(translator, texts)
            for src, tr in zip(batch, translated):
                if ": " in src:
                    off, _ = src.split(": ", 1)
                    # Si l'offset correspond à un nom de Pokémon, applique la traduction officielle
                    orig = skip_offsets_name_map.get(off)
                    if orig:
                        key = norm_name(orig)
                        if key in name_lookup:
                            tr = name_lookup[key]
                    out_lines.append(f"{off}: {tr}")
                else:
                    out_lines.append(tr)
        chunk.write_text("\n".join(out_lines), encoding="utf-8")
        print(f"Traduit {chunk.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Traduction des chunks fr_chunks/chunk_XX.txt")
    parser.add_argument("--only", nargs="*", help="Liste des numéros de chunk à traiter (ex: 02 03 04). Par défaut tous.")
    parser.add_argument("--skip", nargs="*", help="Liste des numéros de chunk à ignorer.")
    args = parser.parse_args()

    to_skip = set(args.skip or [])
    only = set(args.only or [])

    chunks = sorted(CHUNKS_DIR.glob("chunk_*.txt"))
    if only:
        chunks = [c for c in chunks if c.stem.split("_")[1] in only]
    if to_skip:
        chunks = [c for c in chunks if c.stem.split("_")[1] not in to_skip]

    name_lookup = build_name_lookup()
    orig_offsets = load_original_offsets()
    translate_chunks(chunks, orig_offsets, name_lookup)


if __name__ == "__main__":
    main()
