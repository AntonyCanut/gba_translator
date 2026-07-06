"""Unit tests for scripts/audit_english_rom_french_leak.py.

Covers the French detector (precision on English text, recall on French),
the region classifier, and the proximity clusterer. The final tests are
integration guards: when the ROMs are present they assert the known
baked-in French contamination regions are flagged on ``patchedfrenchrom.gba``
(the base-fr build source) and absent from ``englishrom.gba`` (the clean
base used by build-es/build-it/build-de since R-17 "Base Rom").
"""

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

audit = importlib.import_module("audit_english_rom_french_leak")

ENGLISH_ROM = ROOT / "input/roms/englishrom.gba"
FRENCH_ROM = ROOT / "input/roms/patchedfrenchrom.gba"


# ── french_signal: recall on real French ────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Un médicament sous forme de spray.",
    "Concentre des pouvoirs psychiques dans",
    "L'ennemi est tranché\nviolemment.",
    "Lorsque le bourgeon sur son dos éclot,",
    "Il paraît qu'il avale les gens et les",
    "Une boisson très nutritive qui",
])
def test_french_signal_detects_real_french(text):
    assert audit.french_signal(text) is not None


# ── french_signal: precision on English (no false positives) ────────────────

@pytest.mark.parametrize("text", [
    "Sp. Atk rises when burned.",
    "It's a rare Poke Ball that can",             # ascii spelling
    "I'll send your Poke Ball adrift,",
    "Filling up your Pokedex is tough,",
    "I was so happy for my son when he",          # "son" is a French stopword too
    "Powers up with Plus.",                       # "plus" is a French stopword too
    "Weakens non-contact moves.",                 # "non"
    "Farfetch'd. It raises Farfetch'd's",         # English apostrophe, not d'
    "yerself away from ol' Mel for too",          # ol' -> not a French elision
    "The title of Borrius' repeat",               # possessive apostrophe
])
def test_french_signal_ignores_english(text):
    assert audit.french_signal(text) is None


def test_french_signal_masks_pokemon_accent():
    # The é in Poké/Pokémon/Pokédex must never be a French signal on its own.
    assert audit.french_signal("You caught a Pokémon and used a Poké Ball") is None


def test_french_signal_folds_accented_loanwords():
    # "Café"/"Véga" are English loanword/proper-noun, must not flag.
    assert audit.french_signal("I only visit the Café before I have") is None
    assert audit.french_signal("Tell me where they are, Véga!") is None


def test_french_signal_requires_two_distinct_stopwords():
    # A single common stopword is not enough; two distinct ones is French.
    assert audit.french_signal("son corps pour augmenter les stats") is not None


def test_french_signal_rejects_graphics_noise():
    # Pure-accent gibberish with no ascii vowel must not read as French.
    assert audit.french_signal("îîîî ûûûº ºîîû") is None
    assert audit.french_signal("Üîä îöîüî") is None


# ── classify_region ─────────────────────────────────────────────────────────

def test_classify_region_known_tables():
    assert "move names" in audit.classify_region(0x1B2982)
    assert "species names" in audit.classify_region(0x166A981)
    assert "move descriptions" in audit.classify_region(0x0482874)


def test_classify_region_unclassified():
    assert audit.classify_region(0x0000010) == \
        "unclassified (free-space pool or graphics noise)"


# ── cluster_hits ────────────────────────────────────────────────────────────

def test_cluster_hits_merges_near_and_splits_far():
    hits = [
        (0x1000, "accent", "a", "x"),
        (0x1100, "accent", "b", "x"),
        (0x1200, "accent", "c", "x"),
        (0x1300, "accent", "d", "x"),
        (0x1400, "accent", "e", "x"),   # 5 within gap -> one cluster
        (0x9000, "accent", "f", "x"),   # far away, isolated -> dropped (< min)
    ]
    clusters = audit.cluster_hits(hits, gap=0x1000, min_hits=5)
    assert len(clusters) == 1
    assert len(clusters[0]) == 5


def test_cluster_hits_empty():
    assert audit.cluster_hits([]) == []


# ── integration guard on the real ROMs ──────────────────────────────────────

@pytest.mark.rom
@pytest.mark.skipif(not FRENCH_ROM.exists(), reason="patchedfrenchrom.gba not available")
def test_patched_french_rom_ships_french_in_known_regions():
    rom = FRENCH_ROM.read_bytes()
    hits = list(audit.find_french_runs(rom))
    clusters = audit.cluster_hits(hits, min_hits=5)
    regions = {audit.classify_region(c[0][0]) for c in clusters}

    # The move-name and move-description tables and Pokédex flavour are the
    # confirmed baked-in French leaks — they must be flagged. patchedfrenchrom.gba
    # is the deliberately French-patched base build-fr sources from (R-17).
    assert any("move names" in r for r in regions), regions
    assert any("move descriptions" in r for r in regions), regions
    assert any("Pokedex flavour" in r for r in regions), regions

    # Sanity: the leak is substantial, not a stray handful of hits.
    assert sum(len(c) for c in clusters) > 1000


@pytest.mark.rom
@pytest.mark.skipif(not ENGLISH_ROM.exists(), reason="englishrom.gba not available")
def test_english_rom_is_clean_of_known_french_regions():
    # Regression guard for R-17 "Base Rom": englishrom.gba must be the clean
    # vanilla base (build-es/build-it/build-de/build-lang) and must NOT ship
    # the historical French contamination that patchedfrenchrom.gba carries.
    rom = ENGLISH_ROM.read_bytes()
    hits = list(audit.find_french_runs(rom))
    clusters = audit.cluster_hits(hits, min_hits=5)
    regions = {audit.classify_region(c[0][0]) for c in clusters}

    assert "move names" not in regions, regions
    assert "move descriptions" not in regions, regions
    assert "Pokedex flavour" not in regions, regions
