#!/usr/bin/env python3
"""
Réinjecte les textes traduits dans le ROM GBA.

Hypothèses :
- Les textes repérés par offset sont des chaînes terminées par 0xFF (format FireRed).
- On écrase in-place : la nouvelle chaîne doit tenir dans l'espace d'origine
  (longueur originale, terminateur compris). Si elle est plus longue, on signale
  l'erreur et on n'écrit pas.
- Les codes spéciaux {PLAYER}, \n, \p, \l… doivent correspondre à la charmap utilisée.

Usage :
    python inject_translations.py \
        --rom totranslate.gba \
        --charmap charmap_firered.txt \
        --text extracted_text_fr.txt \
        --out totranslate_fr.gba
"""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULT_ROM = Path("totranslate.gba")
DEFAULT_CHARMAP = Path("charmap_firered.txt")
DEFAULT_TEXT = Path("extracted_text_fr.txt")
DEFAULT_OUT = Path("totranslate_fr.gba")

PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")
POINTER_BASE = 0x08000000


def find_free_blocks(data: bytes, min_size: int, align: int = 4):
    """Yield (offset, size) of runs of 0xFF >= min_size with alignment."""
    i = 0
    n = len(data)
    while i < n:
        if data[i] != 0xFF:
            i += 1
            continue
        start = i
        while i < n and data[i] == 0xFF:
            i += 1
        size = i - start
        aligned_start = (start + (align - 1)) // align * align
        usable = size - (aligned_start - start)
        if usable >= min_size:
            yield aligned_start, usable


def load_charmap(path: Path) -> Dict[str, Tuple[int, ...]]:
    """value -> byte sequence (tuple[int])."""
    mapping: Dict[str, Tuple[int, ...]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("@", 1)[0].strip()
        if not line or "=" not in line:
            continue
        left, right = [part.strip() for part in line.rsplit("=", 1)]
        seq = tuple(int(h, 16) for h in right.split())
        if left.startswith("'") and left.endswith("'"):
            val = left[1:-1]
        else:
            val = "{" + left + "}"
        # Conserver la première occurrence si doublons (choix simple)
        if val not in mapping:
            mapping[val] = seq
    # Normaliser l'apostrophe simple sur le même code que '\'' s'il existe
    if "\\'" in mapping and "'" not in mapping:
        mapping["'"] = mapping["\\'"]
    if "’" in mapping and "'" not in mapping:
        mapping["'"] = mapping["’"]
    if '"' not in mapping:
        if "“" in mapping:
            mapping['"'] = mapping["“"]
        elif "”" in mapping:
            mapping['"'] = mapping["”"]
    if "_" not in mapping and "{UNDERSCORE}" in mapping:
        mapping["_"] = mapping["{UNDERSCORE}"]
    return mapping


def parse_offset_line(line: str) -> Tuple[int, str]:
    off_str, text = line.split(": ", 1)
    offset = int(off_str, 16)
    return offset, text


def encode_text(text: str, value_to_seq: Dict[str, Tuple[int, ...]]) -> bytes:
    """Encode une chaîne (avec {TOKENS} et \\n \\p \\l) en bytes + 0xFF final."""
    # Normalisation légère pour éviter les erreurs d'encodage
    text = (
        text.replace("\xa0", " ")
        .replace("\u200b", "")
        .replace("’", "'")
        .replace("‘", "'")
        .replace("«", "“")
        .replace("»", "”")
        .replace('"', "”")
        .replace("—", "-")
        .replace("–", "-")
        .replace("‐", "-")
        .replace("‑", "-")
        .replace("・", ".")
        .replace("•", ".")
        .replace("𝑂", "O")
    )
    out: List[int] = []
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        key: str
        if ch == "\\" and i + 1 < length and text[i + 1] in {"n", "p", "l"}:
            key = "\\" + text[i + 1]
            i += 2
        elif ch == "{":
            end = text.find("}", i)
            if end == -1:
                raise ValueError(f"Accolade fermante manquante dans: {text}")
            key = text[i : end + 1]
            i = end + 1
        else:
            key = ch
            i += 1
        seq = value_to_seq.get(key)
        if seq is None and len(key) == 1:
            seq = value_to_seq.get(" ") or value_to_seq.get("?")
        if seq is None:
            raise KeyError(f"Caractère/tokène non reconnu: {key} dans: {text}")
        out.extend(seq)
    out.append(0xFF)
    return bytes(out)


def try_fit_text(text: str, max_len: int, value_to_seq: Dict[str, Tuple[int, ...]]) -> bytes | None:
    """Tente de compresser/abréger le texte pour tenir dans max_len bytes encodés."""
    # Essai direct
    try:
        enc = encode_text(text, value_to_seq)
        if len(enc) <= max_len:
            return enc
    except Exception:
        pass

    # Remplacements rapides pour gagner de la place
    replacements = [
        ("Pokémon", "PKMN"),
        ("Poké ", "Poke "),
        ("Poké", "Poke"),
        ("Centre PKMN", "Ctr PKMN"),
        ("Centre Pokémon", "Ctr PKMN"),
        ("Boutique", "BTQ"),
        ("Champions", "Champs"),
        ("Champion", "Champ."),
        ("dresseurs", "dres."),
        ("dresseur", "dres."),
        ("Poké Balls", "Poke Balls"),
        ("Poké Ball", "Poke Ball"),
    ]
    comp = text
    for old, new in replacements:
        comp = comp.replace(old, new)
    try:
        enc = encode_text(comp, value_to_seq)
        if len(enc) <= max_len:
            return enc
    except Exception:
        pass

    # Troncature par mots
    words = comp.split()
    while words:
        truncated = " ".join(words)
        try:
            enc = encode_text(truncated, value_to_seq)
            if len(enc) <= max_len:
                return enc
        except Exception:
            pass
        words.pop()  # retire un mot et réessaie

    # Dernier recours : troncature caractère par caractère (évite de laisser l'original)
    trimmed = comp
    while trimmed:
        trimmed = trimmed[:-1]
        try:
            enc = encode_text(trimmed, value_to_seq)
            if len(enc) <= max_len:
                return enc
        except Exception:
            continue
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Réinjecte les traductions dans le ROM GBA.")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM, help="ROM source (.gba)")
    parser.add_argument("--charmap", type=Path, default=DEFAULT_CHARMAP, help="Charmap utilisée")
    parser.add_argument("--text", type=Path, default=DEFAULT_TEXT, help="Fichier de texte traduit")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="ROM de sortie (écrasée si existe)")
    args = parser.parse_args()

    rom_bytes = bytearray(args.rom.read_bytes())
    value_to_seq = load_charmap(args.charmap)

    # Construire un index offset -> taille originale (jusqu'au 0xFF inclus)
    original_lengths: Dict[int, int] = {}
    for line in args.text.read_text(encoding="utf-8").splitlines():
        if ": " not in line:
            continue
        offset, _ = parse_offset_line(line)
        if offset >= len(rom_bytes):
            continue
        end = rom_bytes.find(b"\xFF", offset)
        if end == -1:
            continue
        original_lengths[offset] = end - offset + 1  # inclut le 0xFF

    # Construire un index pointeur -> positions (une seule passe sur le ROM)
    target_ptrs = {POINTER_BASE + off for off in original_lengths.keys()}
    pointer_index: Dict[int, List[int]] = {ptr: [] for ptr in target_ptrs}
    mv = memoryview(rom_bytes)
    for i in range(len(rom_bytes) - 3):
        val = struct.unpack_from("<I", mv, i)[0]
        if val in target_ptrs:
            pointer_index[val].append(i)

    replaced = 0
    moved = 0
    errors: List[str] = []

    free_blocks = list(find_free_blocks(rom_bytes, min_size=16, align=4))
    free_index = 0

    for line_no, line in enumerate(args.text.read_text(encoding="utf-8").splitlines(), 1):
        if ": " not in line:
            continue
        try:
            offset, text = parse_offset_line(line)
            encoded = encode_text(text, value_to_seq)
        except Exception as e:  # capture encode errors
            errors.append(f"Ligne {line_no}: {e}")
            continue

        orig_len = original_lengths.get(offset)
        if orig_len is None:
            errors.append(f"Ligne {line_no}: offset {hex(offset)} introuvable ou sans terminator")
            continue
        if len(encoded) <= orig_len:
            rom_bytes[offset : offset + len(encoded)] = encoded
            if len(encoded) < orig_len:
                rom_bytes[offset + len(encoded) : offset + orig_len] = b"\xFF" * (
                    orig_len - len(encoded)
                )
            replaced += 1
            continue

        # Texte trop long : relogement dans une zone libre
        needed = len(encoded)
        dest_offset = None
        while free_index < len(free_blocks):
            start, size = free_blocks[free_index]
            if size >= needed:
                dest_offset = start
                free_blocks[free_index] = (start + needed, size - needed)
                break
            free_index += 1

        if dest_offset is None:
            errors.append(
                f"Ligne {line_no}: pas d'espace libre pour {len(encoded)} octets (offset {hex(offset)})"
            )
            continue

        rom_bytes[dest_offset : dest_offset + needed] = encoded

        old_ptr_val = POINTER_BASE + offset
        old_ptr = old_ptr_val.to_bytes(4, "little")
        new_ptr = (POINTER_BASE + dest_offset).to_bytes(4, "little")
        positions = pointer_index.get(old_ptr_val, [])
        ptr_replacements = len(positions)
        for idx in positions:
            rom_bytes[idx : idx + 4] = new_ptr
        # éviter de retraiter le même pointeur si jamais rencontré plus tard
        if positions:
            pointer_index[old_ptr_val] = []
        if ptr_replacements == 0:
            # Impossible de reloger sans pointeur : on annule l'écriture et on laisse le texte d'origine
            # tenter d'abord de compresser pour tenir dans l'emplacement d'origine
            fitted = try_fit_text(text, orig_len, value_to_seq)
            if fitted is not None:
                rom_bytes[offset : offset + len(fitted)] = fitted
                if len(fitted) < orig_len:
                    rom_bytes[offset + len(fitted) : offset + orig_len] = b"\xFF" * (
                        orig_len - len(fitted)
                    )
                replaced += 1
                continue
            errors.append(
                f"Ligne {line_no}: texte trop long et aucun pointeur trouvé (offset {hex(offset)}), laissé inchangé"
            )
            # restaurer l'ancienne zone libre (ne pas consommer le bloc)
            free_blocks[free_index] = (dest_offset, free_blocks[free_index][1] + needed)
            continue

        # Libérer l'ancien emplacement pour de futurs relogements
        rom_bytes[offset : offset + orig_len] = b"\xFF" * orig_len
        aligned_old = (offset + 3) // 4 * 4
        usable = orig_len - (aligned_old - offset)
        if usable > 0:
            free_blocks.append((aligned_old, usable))

        moved += 1
        replaced += 1

    args.out.write_bytes(rom_bytes)
    print(f"Chaînes remplacées: {replaced} (déplacées: {moved})")
    if errors:
        print(f"Erreurs ({len(errors)}):")
        for msg in errors[:20]:
            print(" -", msg)
        if len(errors) > 20:
            print(f" … {len(errors)-20} autres")


if __name__ == "__main__":
    main()
