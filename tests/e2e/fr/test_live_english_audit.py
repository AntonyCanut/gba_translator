"""Garde ROM des chaînes entièrement anglaises encore atteignables."""

import json
import struct
from pathlib import Path

import pytest

from scripts.audit_live_english_fr import run_audit
from src.core.collision_check import ROM_BASE, live_target, plausible_sites
from src.core.text_codec import TextDecoder

REPO_ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.rom

TM_HOUSE_TRANSLATIONS = {
    0x1F540CF: ("Ta visite me touche,\nmais tu es si peu aimable.", 1),
    0x1F54276: ("Toutes les bonnes CT", 3),
    0x1F5428A: ("Il y a 120 CT en tout.\nPeux-tu toutes les trouver ?", 1),
    0x1F543BF: ("Ces CT ne vont pas se\ntrouver toutes seules !", 1),
}


@pytest.mark.private_build
def test_every_live_english_string_has_an_explicit_review():
    """Toute nouvelle chaîne anglaise vivante doit être triée explicitement."""
    required = {
        "english_rom": REPO_ROOT / "input/roms/englishrom.gba",
        "french_rom": REPO_ROOT / "output/roms/GenedRom-fr.gba",
        "spanish_rom": REPO_ROOT / "input/roms/spanishrom.gba",
        "extraction": REPO_ROOT
        / "output/extracted/extracted_texts/englishrom_texts.json",
        "reviews_path": REPO_ROOT / "languages/fr/live_english_reviews.yaml",
    }
    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        pytest.skip("artefacts ROM absents: " + ", ".join(missing))

    classification, stale = run_audit(**required)

    assert not classification.unclassified, (
        "chaînes anglaises vivantes non classées: "
        + ", ".join(
            f"{finding.source_offset:#x} {finding.english_text[:60]!r}"
            for finding in classification.unclassified[:20]
        )
    )
    assert not stale, "revues devenues obsolètes: " + ", ".join(stale)
    assert classification.delivered, "le contrôle positif du contenu livré a disparu"
    assert classification.intentional, "la liste explicite d'anglais volontaire est vide"
    assert classification.base_unused, "la liste du contenu de base inutilisé est vide"


def test_tm_house_cluster_is_french_through_every_live_pointer():
    """Les quatre corrections doivent atteindre la ROM, dont les trois titres."""
    english_path = REPO_ROOT / "input/roms/englishrom.gba"
    french_path = REPO_ROOT / "output/roms/GenedRom-fr.gba"
    extraction_path = (
        REPO_ROOT / "output/extracted/extracted_texts/englishrom_texts.json"
    )
    if not all(path.exists() for path in (english_path, french_path, extraction_path)):
        pytest.skip("artefacts ROM absents")

    english = english_path.read_bytes()
    french = french_path.read_bytes()
    entries = json.loads(extraction_path.read_text(encoding="utf-8"))["texts"]
    by_offset = {int(entry["offset"]): entry for entry in entries}

    for source_offset, (expected_text, expected_refs) in TM_HOUSE_TRANSLATIONS.items():
        entry = by_offset[source_offset]
        expected_pointer = struct.pack("<I", ROM_BASE + source_offset)
        raw_sites = [int(value, 0) for value in entry["pointer_offsets"]]
        exact_sites = [
            site
            for site in raw_sites
            if english[site : site + 4] == expected_pointer
        ]
        sites = plausible_sites(english, source_offset, exact_sites)
        assert len(sites) == expected_refs

        for site in sites:
            target = live_target(french, site)
            assert target is not None
            end = french.find(b"\xFF", target, target + 500)
            assert end != -1
            actual_text = TextDecoder.decode_pokemon(
                french[target : end + 1],
                preserve_unknown=True,
            )
            # Le builder réhabille les lignes selon leur largeur après insertion.
            assert " ".join(actual_text.split()) == " ".join(expected_text.split())
