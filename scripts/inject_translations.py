#!/usr/bin/env python3
r"""
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
SENSITIVE_FILE = Path("sensitive_lines.txt")
SENSITIVE_OFFSET_MAX = 0x220000  # zones basses à ne pas reloger (écran de nom, scripts précoces, etc.)
FORCE_SHRINK_OFFSETS = {0x8CEB24, 0x1F0F874}

PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")
POINTER_BASE = 0x08000000
GAP_BYTES = 4  # laisser un petit bloc libre entre deux blocs utilisés


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


def encode_text_truncate(
    text: str, max_len: int, value_to_seq: Dict[str, Tuple[int, ...]]
) -> bytes:
    """Encode en respectant la limite max_len (0xFF inclus) en coupant avant dépassement."""
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
                break
            key = text[i : end + 1]
            i = end + 1
        else:
            key = ch
            i += 1
        seq = value_to_seq.get(key)
        if seq is None and len(key) == 1:
            seq = value_to_seq.get(" ") or value_to_seq.get("?")
        if seq is None:
            continue
        if len(out) + len(seq) + 1 > max_len:  # +1 pour le 0xFF final
            break
        out.extend(seq)
    if len(out) < max_len:
        out.append(0xFF)
    return bytes(out[:max_len])


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


def load_sensitive_lines() -> set[int]:
    if not SENSITIVE_FILE.exists():
        return set()
    out = set()
    for raw in SENSITIVE_FILE.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.add(int(raw))
        except Exception:
            continue
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Réinjecte les traductions dans le ROM GBA.")
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM, help="ROM source (.gba)")
    parser.add_argument("--charmap", type=Path, default=DEFAULT_CHARMAP, help="Charmap utilisée")
    parser.add_argument("--text", type=Path, default=DEFAULT_TEXT, help="Fichier de texte traduit")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="ROM de sortie (écrasée si existe)")
    parser.add_argument(
        "--no-relocate",
        action="store_true",
        help="N'écrit pas hors emplacement original (laisse le texte d'origine si trop long).",
    )
    parser.add_argument(
        "--no-reuse-old-space",
        dest="reuse_old_space",
        action="store_false",
        default=True,
        help="Ne pas réutiliser l'ancien emplacement après relogement.",
    )
    parser.add_argument(
        "--use-holes",
        action="store_true",
        default=True,
        help="Utilise les blocs de 0xFF internes pour reloger (activé par défaut).",
    )
    parser.add_argument(
        "--no-use-holes",
        dest="use_holes",
        action="store_false",
        help="N'utilise pas les blocs 0xFF internes (relogement uniquement en append si autorisé).",
    )
    parser.add_argument(
        "--allow-append",
        action="store_true",
        help="Autorise l'extension de la ROM en fin de fichier si aucune zone libre suffisante n'est trouvée (désactivé par défaut, ROM reste à taille fixe).",
    )
    parser.add_argument(
        "--ignore-sensitive",
        action="store_true",
        help="Ignore la liste des lignes sensibles et la protection des offsets bas.",
    )
    parser.add_argument(
        "--free-map",
        type=Path,
        help="Fichier rom_usage.txt (issu de dump_rom_usage.py) pour forcer les blocs libres à utiliser.",
    )
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
    for i in range(len(rom_bytes) - 3):
        val = int.from_bytes(rom_bytes[i : i + 4], "little")
        if val in target_ptrs:
            pointer_index[val].append(i)

    # Prépare les lignes triées par longueur encodée décroissante (priorité aux plus longues)
    sensitive_lines = load_sensitive_lines()
    entries = []
    line_to_offset: Dict[int, int] = {}
    errors: List[str] = []
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
        line_to_offset[line_no] = offset
        entries.append(
            {
                "line_no": line_no,
                "offset": offset,
                "text": text,
                "encoded": encoded,
                "enc_len": len(encoded),
                "orig_len": orig_len,
                "sensitive": (not args.ignore_sensitive)
                and ((line_no in sensitive_lines) or (offset < SENSITIVE_OFFSET_MAX)),
                "force_shrink": (not args.ignore_sensitive) and (offset in FORCE_SHRINK_OFFSETS),
            }
        )

    entries.sort(key=lambda e: e["enc_len"], reverse=True)

    replaced = 0
    moved = 0
    reuse_from_old = 0

    # free_blocks: liste de (start, size, source) où source ∈ {"hole", "old"}
    if args.free_map:
        free_blocks = []
        for raw in args.free_map.read_text(encoding="utf-8").splitlines():
            parts = raw.split()
            if len(parts) != 4:
                continue
            start, end, size_str, typ = parts
            if typ != "free":
                continue
            try:
                s = int(start, 16)
                sz = int(size_str)
            except Exception:
                continue
            # align
            aligned_start = (s + 3) // 4 * 4
            usable = sz - (aligned_start - s)
            if usable >= 4:
                free_blocks.append((aligned_start, usable, "hole"))
    else:
        free_blocks = (
            [(start, size, "hole") for start, size in find_free_blocks(rom_bytes, min_size=16, align=4)]
            if (not args.no_relocate and args.use_holes)
            else []
        )
    append_offset = (len(rom_bytes) + 3) // 4 * 4  # align fin de rom
    max_rom_size = len(rom_bytes)

    def take_block(needed: int):
        """Retourne un bloc en laissant un écart GAP_BYTES après l'écriture."""
        nonlocal free_blocks
        required = needed + GAP_BYTES
        free_blocks.sort(key=lambda b: (b[2] != "old", b[1]))  # privilégie les blocs libérés, puis best-fit
        for idx, (start, size, src) in enumerate(free_blocks):
            if size >= required:
                alloc_start = start
                remaining_start = start + required
                remaining_size = size - required
                free_blocks[idx] = (remaining_start, remaining_size, src)
                if free_blocks[idx][1] <= 0:
                    free_blocks.pop(idx)
                return alloc_start, src
        return None, None

    for entry in entries:
        line_no = entry["line_no"]
        offset = entry["offset"]
        text = entry["text"]
        encoded = entry["encoded"]
        orig_len = entry["orig_len"]

        # Cas sensible : ne jamais reloger ni changer de pointeur (sauf ignore_sensitive)
        if entry["sensitive"] or args.no_relocate or entry.get("force_shrink"):
            if len(encoded) <= orig_len:
                rom_bytes[offset : offset + len(encoded)] = encoded
                if len(encoded) < orig_len:
                    rom_bytes[offset + len(encoded) : offset + orig_len] = b"\xFF" * (
                        orig_len - len(encoded)
                    )
                replaced += 1
            else:
                fitted = try_fit_text(text, orig_len, value_to_seq)
                if fitted is not None:
                    rom_bytes[offset : offset + len(fitted)] = fitted
                    if len(fitted) < orig_len:
                        rom_bytes[offset + len(fitted) : offset + orig_len] = b"\xFF" * (
                            orig_len - len(fitted)
                        )
                    replaced += 1
                else:
                    errors.append(
                        f"Ligne {line_no}: texte trop long (sensible/force_shrink/no-relo), laissé inchangé (offset {hex(offset)})"
                    )
            continue

        if len(encoded) <= orig_len:
            rom_bytes[offset : offset + len(encoded)] = encoded
            if len(encoded) < orig_len:
                rom_bytes[offset + len(encoded) : offset + orig_len] = b"\xFF" * (
                    orig_len - len(encoded)
                )
            replaced += 1
            continue

        # Texte trop long
        if args.no_relocate:
            end_pos = offset + len(encoded)
            if end_pos > len(rom_bytes):
                rom_bytes.extend(b"\xFF" * (end_pos - len(rom_bytes)))
            rom_bytes[offset:end_pos] = encoded
            replaced += 1
            continue

        # Texte trop long : relogement
        needed = len(encoded)
        dest_offset, source = take_block(needed)

        if dest_offset is None:
            if args.allow_append:
                dest_offset = append_offset
                append_offset += needed
                if append_offset > len(rom_bytes):
                    rom_bytes.extend(b"\xFF" * (append_offset - len(rom_bytes)))
                    if len(rom_bytes) > max_rom_size:
                        max_rom_size = len(rom_bytes)
                source = "append"
            else:
                errors.append(
                    f"Ligne {line_no}: pas d'espace libre pour {len(encoded)} octets (offset {hex(offset)}), laissé inchangé"
                )
                continue

        rom_bytes[dest_offset : dest_offset + needed] = encoded

        old_ptr_val = POINTER_BASE + offset
        new_ptr = (POINTER_BASE + dest_offset).to_bytes(4, "little")
        positions = pointer_index.get(old_ptr_val, [])
        ptr_replacements = len(positions)
        for idx in positions:
            rom_bytes[idx : idx + 4] = new_ptr
        if positions:
            pointer_index[old_ptr_val] = []
        if ptr_replacements == 0:
            # Impossible de reloger sans pointeur : essayer de compresser sinon laisser
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
            # restituer le bloc
            free_blocks.append((dest_offset, needed, source or "hole"))
            continue

        # Libérer l'ancien emplacement pour de futurs relogements
        if args.reuse_old_space:
            rom_bytes[offset : offset + orig_len] = b"\xFF" * orig_len
            aligned_old = (offset + 3) // 4 * 4
            usable = orig_len - (aligned_old - offset)
            if usable > 0:
                free_blocks.append((aligned_old, usable, "old"))

        if source == "old":
            reuse_from_old += 1
        moved += 1
        replaced += 1

    args.out.write_bytes(rom_bytes)
    print(f"Chaînes remplacées: {replaced} (déplacées: {moved}, réutilisation anciens emplacements: {reuse_from_old})")
    if errors:
        print(f"Erreurs ({len(errors)}):")
        for msg in errors[:20]:
            print(" -", msg)
        if len(errors) > 20:
            print(f" … {len(errors)-20} autres")


if __name__ == "__main__":
    main()
