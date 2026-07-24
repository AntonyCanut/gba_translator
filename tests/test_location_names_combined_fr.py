"""
Build-independent unit tests for location-name translations in ``combined_fr.txt``.

Why a *source-level* test (no ROM required)
-------------------------------------------
``tests/test_location_names_fr.py`` validates the **built** ROM
(``output/roms/GenedRom-fr.gba``) and is therefore marked ``@pytest.mark.rom`` —
it can only run *after* a successful ``make build-fr``.

These tests close the gap upstream: they read the **source of truth**
(``combined_fr.txt``) directly, so a silent revert is caught *before* a rebuild
ever happens — in the fast unit profile, on any machine, with no ROM or mGBA.

What they guard against
-----------------------
``combined_fr.txt`` contains ~957 duplicated offsets where **the last entry
wins** (the lowercase block at the bottom of the file is the live one). A fix
script that rewrites a large block — exactly what commit ``c7c1ede`` did — can
silently overwrite an inline World-Map label and revert it to English. These
tests assert that, for every canonical location label offset, the *last-wins*
French value is the expected one and not an English / reverted form.

Scope note
----------
Only the **World-Map label offsets** are asserted to equal a bare location name.
Flowing dialogue legitimately keeps forms like "la Ville de Fallshore"
("the city of Fallshore"), so the English-form guard is deliberately scoped to
the specific label offsets rather than banning the substrings file-wide.

Run standalone:  pytest tests/test_location_names_combined_fr.py -v
Fast profile:    python3 -m pytest tests/ -m "not slow and not stress and not emulator"
"""

import re
from pathlib import Path

import pytest

# combined_fr.txt lives at the repository root, next to the Makefile.
COMBINED_FR = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"

# Line format: "0x<hex offset>: <French text>"  (text may contain ': ' itself)
_LINE_RE = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")


def _load_last_wins() -> dict[int, str]:
    """Parse combined_fr.txt into {offset:int -> French text}, last entry wins.

    Offsets are case-insensitive and zero-padding-insensitive (0x720E74 and
    0x0720e74 are the same key), mirroring the build pipeline's normalization.
    """
    mapping: dict[int, str] = {}
    with COMBINED_FR.open("r", encoding="utf-8", newline="") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n")
            m = _LINE_RE.match(line)
            if not m:
                continue
            offset = int(m.group(1), 16)
            mapping[offset] = m.group(2)  # later occurrence overwrites earlier
    return mapping


# (offset, expected_fr, english_name, banned_english_forms)
# Mirrors WORLD_MAP_LABELS in tests/test_location_names_fr.py, but asserted
# against the *source* file instead of the built ROM. Covers every item listed
# in parent ticket P-29 plus the 2026-06-17/18 follow-up renames.
LOCATION_LABELS = [
    # 'ourg Gurun' (missing leading B) is a *prefix* of the correct value, so it
    # can't be banned as a substring — the exact-match test guards the off-by-1.
    (0xB500A0, "Gurenbourg",      "ourg Gurun (off-by-1 B)", []),
    (0x721304, "Gouffre Gelé",       "Icy Hole",               ["Icy Hole", "Icy hole"]),
    (0x7214E8, "Île Scintillante", "Glimmer Isle",           ["Glimmer Isle", "Glimmer island"]),
    (0x721968, "Épidia",  "Epidimy Town",           ["Epidimy Town"]),
    (0xB50214, "Égouts d'Antésia", "Antisis Sewers",         ["Antisis Sewers"]),
    (0xB5026C, "Mont Foudroyant",  "Thundercap Mt.",     ["Thundercap", "Pic Grondant"]),
    (0xB503CC, "Volcan Cendré",  "Cinder Volcano",         ["Cinder Volcano", "Cendreux"]),
    (0xB514E4, "Daherapolis",           "Dehara City",            ["Dehara City", "Ville de Dehara"]),
    (0xB52274, "Pension Pokémon",  "Pokemon Day Care",       ["Day Care", "Pokemon Day Care"]),
    (0xB522A4, "Polderive",     "Polder Town",            ["Polder Town", "Polder sur Rive"]),
    (0xB531D8, "Île Nouvellune", "Newmoon Island",         ["Newmoon Island"]),
    (0xB535C8, "Île Pleinelune",   "Fullmoon Island",        ["Fullmoon Island"]),
    (0xB537AC, "Rougebois",       "Redwood Village",        ["Redwood Village", "Village Redwood"]),
    (0x720E74, "Rivapolis",        "Fallshore City",         ["Fallshore City", "Ville de Fallshore"]),
    (0x3EEF2D, "Grotte Faille",    "Rift Cave",              ["Rift Cave"]),
    (0xB500F0, "Naville",      "Seaport City",           ["Seaport City", "Ville Portuaire"]),
    (0x3EEFEA, "Grotte de l'Être", "Cave of Being",          ["Cave of Being"]),
    (0x71CA60, "Dresco",           "Dresco Town",            ["Dresco Town"]),
    # Icicle Cave zone-name pop-up. Was inconsistently rendered as the
    # untranslated "Grotte Icicle" and the wrong "Grotte Givre" (Givre belongs
    # to Frost Mountain = "Mont Givre"); canon is "Grotte Stalactite".
    (0x3EEF4B, "Grotte Stalactite", "Icicle Cave",           ["Icicle", "Givre"]),
    # Battle Frontier World-Map label. Was absent from combined_fr.txt entirely,
    # so it rendered untranslated ("Battle Frontier") on the map; canon (used
    # ~30x in-game dialogue) is "Zone de Combat".
    (0xB535E4, "Zone de Combat",    "Battle Frontier",        ["Battle Frontier", "Frontier"]),
]

# Icicle Cave is referenced by these flowing-text / signpost offsets. They are
# not bare labels (so no exact-match), but their live value must use the canon
# "Grotte Stalactite" and never the untranslated "Grotte Icicle".
ICICLE_CAVE_TEXT_OFFSETS = [
    0x1F561CE,  # "Va à la Grotte Stalactite, apporte le Pokédex à ..."
    0x1F57BCA,  # Raid-den location note (hidden section)
    0x1F70ABD,  # "Grotte Stalactite\nPassage" signpost
]

# Reverted forms from the c7c1ede regression that B-52 recovered; none of them
# may resurface as the *live* (last-wins) value of its canonical label offset.
C7C1EDE_REGRESSION = [
    (0xB535C8, "Fullmoon Island"),
    (0x720E74, "Ville de Fallshore"),
    (0xB514E4, "Ville de Dehara"),
]


@pytest.fixture(scope="module")
def combined() -> dict[int, str]:
    if not COMBINED_FR.is_file():
        pytest.fail(f"Source of truth not found: {COMBINED_FR}")
    return _load_last_wins()


class TestLocationNamesCombinedFR:
    """Every location label in combined_fr.txt must resolve to its French name."""

    def test_source_file_exists_and_parses(self, combined):
        """Sanity: combined_fr.txt parses into a non-trivial offset map."""
        assert len(combined) > 1000, (
            f"Parsed only {len(combined)} offsets from {COMBINED_FR.name}; "
            "the file format may have changed."
        )

    @pytest.mark.parametrize(
        "offset, expected_fr, en_name",
        [(o, fr, en) for (o, fr, en, _bad) in LOCATION_LABELS],
        ids=[en for (_o, _fr, en, _bad) in LOCATION_LABELS],
    )
    def test_label_translation_matches(self, combined, offset, expected_fr, en_name):
        """Last-wins value for each label offset equals the canonical French name."""
        assert offset in combined, (
            f"Offset 0x{offset:06X} [{en_name}] is missing from combined_fr.txt — "
            "the World-Map label entry was dropped."
        )
        actual = combined[offset].strip()
        assert actual == expected_fr, (
            f"Label 0x{offset:06X} [{en_name}]: expected {expected_fr!r}, "
            f"got {actual!r} (a fix script likely overwrote the live entry)."
        )

    @pytest.mark.parametrize(
        "offset, expected_fr, en_name, banned",
        LOCATION_LABELS,
        ids=[en for (_o, _fr, en, _bad) in LOCATION_LABELS],
    )
    def test_label_has_no_english_form(self, combined, offset, expected_fr, en_name, banned):
        """No English / reverted form leaks into a label's live value."""
        actual = combined.get(offset, "")
        for bad in banned:
            assert bad not in actual, (
                f"Label 0x{offset:06X} [{en_name}] still contains the "
                f"English/reverted form {bad!r}: {actual!r}"
            )

    @pytest.mark.parametrize(
        "offset, reverted",
        C7C1EDE_REGRESSION,
        ids=[f"{o:06X}:{r}" for (o, r) in C7C1EDE_REGRESSION],
    )
    def test_no_c7c1ede_revert_at_label(self, combined, offset, reverted):
        """The c7c1ede-class reverts must never be the live value at their label."""
        actual = combined.get(offset, "")
        assert actual.strip() != reverted, (
            f"Regression: label 0x{offset:06X} reverted to {reverted!r} "
            "(the c7c1ede overwrite resurfaced)."
        )

    @pytest.mark.parametrize("offset", ICICLE_CAVE_TEXT_OFFSETS,
                             ids=[f"{o:06X}" for o in ICICLE_CAVE_TEXT_OFFSETS])
    def test_icicle_cave_text_uses_canon(self, combined, offset):
        """Icicle Cave references must use "Grotte Stalactite", never "Grotte Icicle"."""
        actual = combined.get(offset, "")
        assert offset in combined, f"Offset 0x{offset:06X} missing from combined_fr.txt."
        assert "Grotte Stalactite" in actual, (
            f"0x{offset:06X}: expected the canon 'Grotte Stalactite', got {actual!r}."
        )
        assert "Grotte Icicle" not in actual, (
            f"0x{offset:06X}: untranslated 'Grotte Icicle' resurfaced: {actual!r}."
        )

    def test_chenal_aubrun_is_systematically_masculine(self, combined):
        """Toutes les mentions du Chenal Aubrun emploient un article masculin."""
        references = {
            offset: text
            for offset, text in combined.items()
            if "Chenal Aubrun" in text
        }
        assert references, "Aucune mention du Chenal Aubrun dans combined_fr.txt."

        feminine_forms = ("la Chenal Aubrun", "de la Chenal Aubrun", "à la Chenal Aubrun")
        violations = [
            f"0x{offset:06X}: {text}"
            for offset, text in references.items()
            if any(form in text for form in feminine_forms)
        ]
        assert not violations, (
            "Le toponyme masculin « Chenal Aubrun » conserve un accord féminin :\n"
            + "\n".join(violations)
        )

    def test_last_wins_semantics_for_fallshore(self, combined):
        """0x720E74 is duplicated; the loader must keep the *last* entry ('Fallshore').

        Guards the parser itself: an earlier duplicate says 'Ville de Fallshore',
        the live (bottom-block) entry says 'Fallshore'. If last-wins ever breaks,
        every other assertion here would silently test the wrong entry.
        """
        with COMBINED_FR.open("r", encoding="utf-8") as fh:
            dupes = [ln for ln in fh if re.match(r"^0x0*720[eE]74:", ln)]
        assert len(dupes) >= 2, (
            "Expected 0x720E74 to be duplicated in combined_fr.txt to exercise "
            f"last-wins; found {len(dupes)} occurrence(s)."
        )
        assert combined[0x720E74].strip() == "Rivapolis"


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
