"""Gardes du glossaire Pokémon allemand figé par F-599."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from languages.de.patches import item_names, move_names, nature_names
from languages.fr.patches import ability_names as ability_table
from languages.fr.patches import move_names as move_table

ROOT = Path(__file__).resolve().parents[3]
GLOSSARY_PATH = ROOT / "languages/de/data/official_terminology.yaml"
MOVE_GLOSSARY_PATH = ROOT / "languages/de/data/move_names_de_official.json"


def _glossary() -> dict:
    return yaml.safe_load(GLOSSARY_PATH.read_text(encoding="utf-8"))


def _combined_entries() -> dict[int, str]:
    return ability_table._parse_combined(ROOT / "languages/de/combined_de.txt")


def test_glossary_freezes_sources_and_core_official_terms() -> None:
    glossary = _glossary()

    assert glossary["schema_version"] == 1
    assert glossary["sources"]["pokemon_type_chart"]["url"].startswith(
        "https://assets.pokemon.com/"
    )
    assert len(glossary["sources"]["pokeapi"]["commit"]) == 40
    assert glossary["types"] == {
        "Normal": "Normal",
        "Fighting": "Kampf",
        "Flying": "Flug",
        "Poison": "Gift",
        "Ground": "Boden",
        "Rock": "Gestein",
        "Bug": "Käfer",
        "Ghost": "Geist",
        "Steel": "Stahl",
        "Fire": "Feuer",
        "Water": "Wasser",
        "Grass": "Pflanze",
        "Electric": "Elektro",
        "Psychic": "Psycho",
        "Ice": "Eis",
        "Dragon": "Drache",
        "Dark": "Unlicht",
        "Fairy": "Fee",
    }
    assert glossary["stats"] == {
        "HP": "KP",
        "Attack": "Angriff",
        "Defense": "Verteidigung",
        "Special Attack": "Spezialangriff",
        "Special Defense": "Spezialverteidigung",
        "Speed": "Initiative",
        "accuracy": "Genauigkeit",
        "evasion": "Fluchtwert",
    }


def test_natures_match_the_frozen_glossary() -> None:
    assert list(nature_names.TARGETS.values()) == list(_glossary()["natures"].values())


def test_ability_and_item_corrections_match_the_frozen_glossary() -> None:
    glossary = _glossary()
    combined = _combined_entries()
    english = ability_table._parse_combined(ROOT / "languages/en/combined_en.txt")
    ability_by_english = {
        english[offset]: combined[offset]
        for offset in combined
        if offset in english
        and ability_table.ABILITY_TABLE_OFFSET
        <= offset
        <= ability_table.ABILITY_TABLE_LAST
    }

    for english_name, german_name in glossary["ability_corrections"].items():
        assert ability_by_english[english_name] == german_name
    for english_name, german_name in glossary["item_corrections"].items():
        assert item_names.ALL_NAMES[english_name] == german_name


def test_move_glossary_is_cfru_aligned_and_complete() -> None:
    entries = json.loads(MOVE_GLOSSARY_PATH.read_text(encoding="utf-8"))

    assert len(entries) == move_table.MOVE_COUNT
    assert entries["2"] == {
        "english": "Karate Chop",
        "official": "Karateschlag",
        "source": "pokeapi",
    }
    assert entries["587"]["english"] == "Fire Lash"
    assert entries["587"]["official"] == "Feuerpeitsche"


def test_move_patch_never_substitutes_another_move_for_an_overflow() -> None:
    translations = move_names.load_translations()

    karate_chop = move_table.LEGACY_TABLE_OFFSET + 2 * move_table.MOVE_STRIDE
    fire_lash = move_table.LEGACY_TABLE_OFFSET + 587 * move_table.MOVE_STRIDE
    brick_break = move_table.LEGACY_TABLE_OFFSET + 280 * move_table.MOVE_STRIDE

    assert translations[karate_chop] == "Karateschlag"
    assert translations[brick_break] == "Durchbruch"
    assert translations[fire_lash] == "Feuerpeitsc."
    assert translations[fire_lash] != "Feenschloss"
    assert move_names._fits_cell(translations[fire_lash])


def test_constraint_policy_forbids_language_fallbacks() -> None:
    policy = _glossary()["constrained_cells"]

    assert policy["fallback_languages"] == []
    assert policy["move_names"]["max_glyphs"] == 12
    assert policy["item_names"]["max_glyphs"] == 13
    assert policy["ability_names"]["max_glyphs"] == 16
