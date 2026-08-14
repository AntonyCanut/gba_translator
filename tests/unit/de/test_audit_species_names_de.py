"""Regression tests for the German ROM species-name leak audit."""

from __future__ import annotations

import struct
from pathlib import Path

from languages.de.tools.audit_species_names import (
    audit_combined,
    audit_live_pointer_texts,
    find_french_species_names,
    load_french_aliases,
)
from languages.fr.patches.species_names import SPECIES_TABLE_OFFSET
from src.core.text_codec import TextEncoder

ROOT = Path(__file__).resolve().parents[3]


def test_finds_french_species_names_without_touching_dynamic_variables():
    aliases = {"Dracaufeu": "Charizard", "Évoli": "Eevee"}
    text = (
        "{STR_VAR_1} rejoint {COLOR}ÇDracaufeu{COLOR}Ë, "
        "puis {B_ATK_NAME_WITH_PREFIX}."
    )

    assert find_french_species_names(text, aliases) == [("Dracaufeu", "Charizard")]
    assert find_french_species_names(r"Combat!\pÉvoli arrive.", aliases) == [
        ("Évoli", "Eevee")
    ]
    assert "{STR_VAR_1}" in text
    assert "{B_ATK_NAME_WITH_PREFIX}" in text


def test_french_name_shared_with_german_localisation_is_still_a_leak():
    aliases = load_french_aliases()

    assert aliases["Kapoera"] == "Hitmontop"
    assert find_french_species_names("Kapoera!", aliases) == [
        ("Kapoera", "Hitmontop")
    ]


def test_combined_audit_obeys_last_entry_wins(tmp_path: Path):
    combined = tmp_path / "combined_de.txt"
    combined.write_text(
        "0x100: Dracaufeu ancien\n"
        "0x100: Charizard aktuell\n"
        "0x200: Geschenk: Carapuce\n",
        encoding="utf-8",
    )

    leaks = audit_combined(
        combined,
        {"Dracaufeu": "Charizard", "Carapuce": "Squirtle"},
    )

    assert [(leak.offset, leak.french, leak.english) for leak in leaks] == [
        (0x200, "Carapuce", "Squirtle")
    ]


def test_combined_audit_includes_fixed_species_table(tmp_path: Path):
    combined = tmp_path / "combined_de.txt"
    combined.write_text(
        f"0x{SPECIES_TABLE_OFFSET:X}: Kapoera\n",
        encoding="utf-8",
    )

    leaks = audit_combined(combined, {"Kapoera": "Hitmontop"})

    assert [(leak.offset, leak.french, leak.english) for leak in leaks] == [
        (SPECIES_TABLE_OFFSET, "Kapoera", "Hitmontop")
    ]


def test_rom_audit_follows_relocated_live_pointer():
    source_offset = 0x100
    relocated_offset = 0x200
    pointer_site = 0x20
    english = bytearray(b"\x00" * 0x300)
    target = bytearray(b"\x00" * 0x300)
    struct.pack_into("<I", english, pointer_site, 0x08000000 + source_offset)
    struct.pack_into("<I", target, pointer_site, 0x08000000 + relocated_offset)
    english[source_offset : source_offset + 10] = (
        TextEncoder.encode_pokemon("Charizard") + b"\xff"
    )
    target[relocated_offset : relocated_offset + 11] = (
        TextEncoder.encode_pokemon("Dracaufeu") + b"\xff"
    )

    leaks = audit_live_pointer_texts(
        bytes(english),
        bytes(target),
        [source_offset],
        {"Dracaufeu": "Charizard"},
    )

    assert len(leaks) == 1
    assert leaks[0].source_offset == source_offset
    assert leaks[0].pointer_site == pointer_site
    assert leaks[0].target_offset == relocated_offset
    assert leaks[0].french == "Dracaufeu"


def test_rom_audit_scans_live_pointer_absent_from_combined_offsets():
    source_offset = 0x100
    relocated_offset = 0x200
    pointer_site = 0x20
    english = bytearray(b"\x00" * 0x300)
    target = bytearray(b"\x00" * 0x300)
    struct.pack_into("<I", english, pointer_site, 0x08000000 + source_offset)
    struct.pack_into("<I", target, pointer_site, 0x08000000 + relocated_offset)
    english[source_offset : source_offset + 10] = (
        TextEncoder.encode_pokemon("Hitmontop") + b"\xff"
    )
    target[relocated_offset : relocated_offset + 8] = (
        TextEncoder.encode_pokemon("Kapoera") + b"\xff"
    )

    leaks = audit_live_pointer_texts(
        bytes(english),
        bytes(target),
        None,
        {"Kapoera": "Hitmontop"},
    )

    assert [(leak.source_offset, leak.pointer_site, leak.french) for leak in leaks] == [
        (source_offset, pointer_site, "Kapoera")
    ]


def test_live_german_source_contains_no_french_species_names():
    leaks = audit_combined(
        ROOT / "languages/de/combined_de.txt",
        load_french_aliases(),
    )

    assert leaks == []
