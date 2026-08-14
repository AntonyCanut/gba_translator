#!/usr/bin/env python3
"""Audit the German source and built ROM for French Pokémon species names.

The fixed species table is compared as raw bytes with the English source.
Pointer-based text is checked at the target reached by each live English
pointer, so relocated dialogue is audited rather than dead source bytes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from languages.de.patches.species_names import (  # noqa: E402
    ENGLISH_ROM,
    SPECIES_TABLE_END,
)
from languages.fr.patches.species_names import SPECIES_TABLE_OFFSET  # noqa: E402
from src.core.collision_check import (  # noqa: E402
    build_pointer_index,
    live_target,
    plausible_sites,
)
from src.core.text_codec import TextDecoder  # noqa: E402

DE_COMBINED = REPO_ROOT / "languages/de/combined_de.txt"
DE_NAME_REFERENCE = REPO_ROOT / "languages/de/data/species_names_de_fallback.json"
FR_NAME_MAP = REPO_ROOT / "languages/fr/data/pokemon_names_en_fr.json"
DEFAULT_ROM = REPO_ROOT / "output/roms/GenedRom-de.gba"
LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
WORD_CHARS = r"A-Za-zÀ-ÖØ-öø-ÿ"

# "Draco Meteor" is the official German move name, not the French species
# name Draco.  Ignore only that exact lexical use; a standalone Draco remains
# a leak.
IGNORED_PHRASES = {"Draco": ("Draco Meteor",)}


@dataclass(frozen=True)
class CombinedLeak:
    offset: int
    french: str
    english: str
    text: str


@dataclass(frozen=True)
class RomLeak:
    source_offset: int
    pointer_site: int
    target_offset: int
    french: str
    english: str
    text: str


def load_french_aliases(
    name_map: Path = FR_NAME_MAP,
    german_reference: Path = DE_NAME_REFERENCE,
) -> dict[str, str]:
    """Return unambiguous French-only species name -> canonical EN name."""
    french = json.loads(name_map.read_text(encoding="utf-8"))["pokemon_names"]
    german_names = set(
        json.loads(german_reference.read_text(encoding="utf-8")).values()
    )
    return {
        fr_name: en_name
        for en_name, fr_name in french.items()
        if fr_name != en_name and fr_name not in german_names
    }


def _alias_pattern(aliases: Mapping[str, str]) -> re.Pattern[str] | None:
    if not aliases:
        return None
    alternatives = "|".join(
        re.escape(name) for name in sorted(aliases, key=len, reverse=True)
    )
    return re.compile(rf"({alternatives})", re.IGNORECASE)


def _has_species_boundaries(text: str, start: int, end: int) -> bool:
    """Treat the palette byte after ``{COLOR}`` as control data, not a word."""
    left_is_word = start > 0 and re.match(rf"[{WORD_CHARS}]", text[start - 1])
    left_is_color_control = bool(re.search(r"\{COLOR\}.$", text[:start]))
    left_is_break_control = bool(re.search(r"\\[nlp]$", text[:start]))
    right_is_word = end < len(text) and re.match(rf"[{WORD_CHARS}]", text[end])
    return (
        not left_is_word or left_is_color_control or left_is_break_control
    ) and not right_is_word


def find_french_species_names(
    text: str,
    aliases: Mapping[str, str],
) -> list[tuple[str, str]]:
    """Find French species lexemes without expanding runtime name variables."""
    pattern = _alias_pattern(aliases)
    if pattern is None:
        return []
    canonical = {name.casefold(): (name, english) for name, english in aliases.items()}
    found: list[tuple[str, str]] = []
    for match in pattern.finditer(text):
        if not _has_species_boundaries(text, match.start(), match.end()):
            continue
        french, english = canonical[match.group(1).casefold()]
        ignored = IGNORED_PHRASES.get(french, ())
        if any(text[match.start() :].casefold().startswith(p.casefold()) for p in ignored):
            continue
        found.append((french, english))
    return found


def load_combined_entries(path: Path) -> dict[int, str]:
    """Load live combined entries using the build's last-entry-wins rule."""
    entries: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = LINE_RE.match(line)
        if match:
            entries[int(match.group(1), 16)] = match.group(2)
    return entries


def audit_combined(
    combined: Path,
    aliases: Mapping[str, str],
) -> list[CombinedLeak]:
    leaks: list[CombinedLeak] = []
    for offset, text in load_combined_entries(combined).items():
        if SPECIES_TABLE_OFFSET <= offset < SPECIES_TABLE_END:
            continue
        for french, english in find_french_species_names(text, aliases):
            leaks.append(CombinedLeak(offset, french, english, text))
    return leaks


def _decode_at(rom: bytes, offset: int, limit: int = 4096) -> str:
    end = rom.find(b"\xff", offset, min(len(rom), offset + limit))
    if end == -1:
        end = min(len(rom), offset + limit)
    else:
        end += 1
    return TextDecoder.decode_pokemon(rom[offset:end], preserve_unknown=True)


def audit_live_pointer_texts(
    english: bytes,
    target: bytes,
    source_offsets: Iterable[int],
    aliases: Mapping[str, str],
) -> list[RomLeak]:
    """Follow every plausible EN pointer site in the target and inspect text."""
    en_index = build_pointer_index(english)
    leaks: list[RomLeak] = []
    seen: set[tuple[int, int, int, str]] = set()
    for source_offset in sorted(set(source_offsets)):
        sites = plausible_sites(
            english,
            source_offset,
            en_index.get(source_offset, ()),
        )
        for site in sites:
            target_offset = live_target(target, site)
            if target_offset is None:
                continue
            text = _decode_at(target, target_offset)
            for french, canonical in find_french_species_names(text, aliases):
                key = (source_offset, site, target_offset, french)
                if key in seen:
                    continue
                seen.add(key)
                leaks.append(
                    RomLeak(
                        source_offset,
                        site,
                        target_offset,
                        french,
                        canonical,
                        text,
                    )
                )
    return leaks


def audit_rom(
    rom_path: Path,
    english_path: Path = ENGLISH_ROM,
    combined: Path = DE_COMBINED,
    aliases: Mapping[str, str] | None = None,
) -> tuple[bool, list[RomLeak]]:
    english = english_path.read_bytes()
    target = rom_path.read_bytes()
    table_matches = (
        len(english) >= SPECIES_TABLE_END
        and len(target) >= SPECIES_TABLE_END
        and target[SPECIES_TABLE_OFFSET:SPECIES_TABLE_END]
        == english[SPECIES_TABLE_OFFSET:SPECIES_TABLE_END]
    )
    source_offsets = load_combined_entries(combined)
    rom_leaks = audit_live_pointer_texts(
        english,
        target,
        source_offsets,
        aliases or load_french_aliases(),
    )
    return table_matches, rom_leaks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--english", type=Path, default=ENGLISH_ROM)
    parser.add_argument("--combined", type=Path, default=DE_COMBINED)
    args = parser.parse_args(argv)

    aliases = load_french_aliases()
    source_leaks = audit_combined(args.combined, aliases)
    table_matches, rom_leaks = audit_rom(
        args.rom,
        english_path=args.english,
        combined=args.combined,
        aliases=aliases,
    )
    print(f"Species table EN byte match: {'yes' if table_matches else 'NO'}")
    print(f"French species leaks in live DE source entries: {len(source_leaks)}")
    print(f"French species leaks through live ROM pointers: {len(rom_leaks)}")
    for leak in source_leaks[:50]:
        print(
            f"  source 0x{leak.offset:X}: {leak.french} -> {leak.english}: "
            f"{leak.text[:120]}"
        )
    for leak in rom_leaks[:50]:
        print(
            f"  ROM ptr 0x{leak.pointer_site:X} -> 0x{leak.target_offset:X}: "
            f"{leak.french} -> {leak.english}"
        )
    return 0 if table_matches and not source_leaks and not rom_leaks else 1


if __name__ == "__main__":
    raise SystemExit(main())
