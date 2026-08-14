"""Gardes globales des libellés courts de l'interface allemande."""

from __future__ import annotations

import re
from pathlib import Path

from languages.de.patches import (
    dexnav_headers,
    levelup_stat_abbreviations,
    options_footer,
    pc_messages,
    shop,
)
from src.i18n import load_registry

ROOT = Path(__file__).resolve().parents[3]
COMBINED_DE = ROOT / "languages" / "de" / "combined_de.txt"
FORBIDDEN_HP_FORMS = re.compile(r"(?<![A-Za-zÄÖÜäöüß])(HP|PS|PV)(?![A-Za-zÄÖÜäöüß])")


def _combined_values() -> list[tuple[int, str]]:
    values: list[tuple[int, str]] = []
    entry = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
    for line in COMBINED_DE.read_text(encoding="utf-8").splitlines():
        match = entry.match(line)
        if match:
            values.append((int(match.group(1), 16), match.group(2)))
    return values


def test_cfru_de_strings_forbid_hp_ps_and_pv() -> None:
    offenders = [
        (offset, match.group(0), value)
        for offset, value in _combined_values()
        if (match := FORBIDDEN_HP_FORMS.search(value))
    ]

    assert offenders == [], "résidus HP/PS/PV dans combined_de.txt: " + "; ".join(
        f"0x{offset:X}={token!r} dans {value!r}"
        for offset, token, value in offenders
    )


def test_status_abbreviations_are_official_and_consistent() -> None:
    assert load_registry().get("de").status_abbrev == {
        "poison": "GIF",
        "burn": "VBR",
        "freeze": "GEF",
        "paralysis": "PAR",
        "sleep": "SCH",
        "faint": "KO",
    }


def test_levelup_stat_abbreviations_are_german_and_fit_the_cells() -> None:
    entries = levelup_stat_abbreviations._LEVELUP_ABBREVS

    assert [entry["de"] for entry in entries] == ["Ang.Sp.", "Ver.Sp."]
    for entry in entries:
        assert len(levelup_stat_abbreviations._encode(entry["de"])) <= len(
            levelup_stat_abbreviations._encode(entry["en"])
        )
        assert FORBIDDEN_HP_FORMS.search(entry["de"]) is None


def test_dexnav_word_images_use_german_labels_within_tile_budgets() -> None:
    assert [header[3] for header in dexnav_headers.HEADERS] == [
        "SUCHLEVEL",
        "METHODE",
        "VERST. FAEH.",
        "ITEMS",
    ]
    for _row, _first_tile, tile_count, label, _known_good in dexnav_headers.HEADERS:
        assert dexnav_headers._text_width(label) <= tile_count * 8
        assert FORBIDDEN_HP_FORMS.search(label) is None


def test_fixed_ui_patches_forbid_hp_ps_and_pv() -> None:
    labels = [
        *options_footer.DE_WORDS,
        shop._BUY_DE_TEXT,
        *(patch[2] for patch in pc_messages.PATCHES),
    ]

    assert all(FORBIDDEN_HP_FORMS.search(label) is None for label in labels)
    assert len(options_footer._build_de_bytes()) + 1 <= options_footer.SLOT_SIZE
