"""Unit tests for scripts/translate_pokemon_names_in_dialogue_fr.py.

The script localises English Pokémon species names left inside French
dialogue (``Tu as un beau Charizard !`` -> ``… Dracaufeu !``) and raises an
alert whenever the longer French name breaks the dialogue (line overflow or
broken article elision). These tests pin the matching, the token/gang
safeguards, and the alert detection.
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "translate_pokemon_names_in_dialogue_fr.py"

spec = importlib.util.spec_from_file_location("translate_pokemon_names_fr", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

NAME_MAP = {
    "Charizard": "Dracaufeu",
    "Oddish": "Mystherbe",
    "Ferrothorn": "Noacier",
    "Emboar": "Roitiflam",
    "Pikachu": "Pikachu",  # identical: load_name_map drops these
    "Lapras": "Lokhlass",
}


def _matcher(name_map=None):
    nm = name_map or {k: v for k, v in NAME_MAP.items() if k != v}
    return nm, mod.build_matcher(nm)


def _translate(text, name_map=None):
    nm, matcher = _matcher(name_map)
    return mod.translate_segment(text, matcher, nm, {})


# --- core matching ---------------------------------------------------------

def test_whole_word_name_is_translated():
    assert _translate("Tu as un beau Charizard !") == "Tu as un beau Dracaufeu !"


def test_match_is_case_sensitive():
    # a lowercase common word must never be hit
    assert _translate("oddish n'est pas un nom propre") == (
        "oddish n'est pas un nom propre"
    )


def test_substring_is_not_matched():
    # whole-word boundary: no firing inside a longer token
    assert _translate("Charizardite") == "Charizardite"


def test_identical_name_is_dropped_from_the_map():
    # Pikachu == Pikachu in both languages, so it is never a candidate
    nm = {k: v for k, v in NAME_MAP.items() if k != v}
    assert "Pikachu" not in nm
    assert _translate("J'adore Pikachu !") == "J'adore Pikachu !"


# --- gang proper-noun safeguards ------------------------------------------

def test_english_gang_name_is_preserved():
    assert _translate("Les Black Ferrothorn arrivent.") == (
        "Les Black Ferrothorn arrivent."
    )


def test_french_gang_name_is_preserved():
    assert _translate("avoir terminé « L'Emboar Noir ».") == (
        "avoir terminé « L'Emboar Noir »."
    )


def test_real_mention_next_to_gang_still_translates():
    # only the gang-affixed occurrence is spared
    assert _translate("Un Ferrothorn sauvage, pas les Black Ferrothorn.") == (
        "Un Noacier sauvage, pas les Black Ferrothorn."
    )


# --- token preservation ----------------------------------------------------

def test_control_tokens_are_left_intact():
    text = "{COLOR}ÇCharizard{STR_VAR_1} !"
    assert _translate(text) == "{COLOR}ÇDracaufeu{STR_VAR_1} !"


def test_name_inside_a_token_is_not_touched():
    # a species substring living inside a brace token stays verbatim
    text = "{B_LAPRAS_NAME} arrive"
    assert _translate(text) == "{B_LAPRAS_NAME} arrive"


# --- width measurement -----------------------------------------------------

def test_color_token_does_not_inflate_width():
    bare = mod.line_pixel_widths("Magcargo!")
    tagged = mod.line_pixel_widths("{COLOR}ÇMagcargo!")
    assert bare == tagged  # {COLOR} + its palette char render nothing


def test_structural_breaks_split_visual_lines():
    widths = mod.line_pixel_widths("abc\\ndef\\pghi\\ljkl")
    assert len(widths) == 4


def test_overflow_regression_flags_a_line_that_grows_past_the_box():
    long_fr = "x" * 200
    nm = {"Foo": long_fr}
    regressed, widths = mod.overflow_regression("un Foo court", "un " + long_fr + " court")
    assert regressed is True
    assert max(widths) > mod.DEFAULT_MAX_LINE_WIDTH


def test_overflow_regression_quiet_when_name_shorter():
    regressed, _ = mod.overflow_regression(
        "Vous recevez un Charizard.", "Vous recevez un D...."
    )
    assert regressed is False


# --- elision detection -----------------------------------------------------

def test_elision_matcher_flags_broken_apostrophe():
    nm = {k: v for k, v in NAME_MAP.items() if k != v}
    em = mod.build_elision_matcher(nm)
    # Oddish (vowel) -> Mystherbe (consonant): "d'Mystherbe" is wrong
    assert em.search("Feuilles d'Mystherbe") is not None


def test_elision_matcher_quiet_on_valid_elision():
    nm = {k: v for k, v in NAME_MAP.items() if k != v}
    em = mod.build_elision_matcher(nm)
    # "de Dracaufeu" / a vowel-initial FR name elides fine -> no alert
    assert em.search("de Dracaufeu") is None
    assert em.search("le Dracaufeu") is None


# --- full pipeline ---------------------------------------------------------

def test_process_translates_and_reports_alert():
    nm = {k: v for k, v in NAME_MAP.items() if k != v}
    matcher = mod.build_matcher(nm)
    em = mod.build_elision_matcher(nm)
    lines = [
        "0x001: Tu as un beau Charizard !",            # clean translation
        "0x002: des Feuilles d'Oddish à vendre",        # elision regression
        "0x003: Les Black Emboar sont là.",             # gang, preserved
        "0x004: Oddish",                                # bare table cell, skipped
        "# a comment line without a colon-offset",
    ]
    new_lines, counts, alerts = mod.process(lines, nm, matcher, em)

    assert new_lines[0] == "0x001: Tu as un beau Dracaufeu !"
    assert new_lines[2] == "0x003: Les Black Emboar sont là."   # untouched
    assert new_lines[3] == "0x004: Oddish"                       # bare cell skipped
    assert counts["Charizard"] == 1
    offsets = {a["offset"] for a in alerts}
    assert "0x002" in offsets
    elide = next(a for a in alerts if a["offset"] == "0x002")
    assert "elision" in elide["reasons"]


# --- end-to-end guard on the real, applied combined_fr.txt -----------------

COMBINED = REPO / "combined_fr.txt"


def test_applied_combined_is_idempotent_and_alert_free():
    """The names are already localised in the live source: a fresh pass must
    find nothing left to translate and raise no overflow/elision alert."""
    name_map = mod.load_name_map()
    matcher = mod.build_matcher(name_map)
    elision = mod.build_elision_matcher(name_map)
    lines = COMBINED.read_text(encoding="utf-8").splitlines()
    new_lines, counts, alerts = mod.process(lines, name_map, matcher, elision)
    assert sum(counts.values()) == 0, "English species names still present in dialogue"
    assert alerts == [], "an unaddressed dialogue overflow/elision remains"
    assert new_lines == lines


def test_gang_proper_nouns_are_preserved_in_source():
    text = COMBINED.read_text(encoding="utf-8")
    # English gang form kept verbatim, never half-translated to franglais
    assert "Black Ferrothorn" in text and "Black Emboar" in text
    assert "Black Noacier" not in text and "Black Roitiflam" not in text
    # no broken elision such as « d'Mystherbe » survived the apply step
    assert "d'Mystherbe" not in text
