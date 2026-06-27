"""Regression tests for ellipsis-pause restoration (ticket R-09 follow-up #2).

R-09 *deleted* the ex-ellipsis quote glyphs (English byte 0xB0 = "…") that had
been decoded into combined_fr.txt as straight double quotes. Deletion threw away
the intended pause ("Bref" tu vois" → "Bref tu vois" instead of "Bref… tu
vois"). This restores them as the raw 1-byte 0xB0 glyph (rendered as "…"),
which is byte-faithful to the English source and keeps each entry in its
in-place slot. See scripts/restore_ellipsis_pauses_fr.py.
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "restore_ellipsis_pauses_fr.py"
COMBINED = REPO / "languages/fr/combined_fr.txt"

spec = importlib.util.spec_from_file_location("restore_ellipsis_pauses_fr", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

B0 = mod.ELLIPSIS  # "<0xB0>"


# --- pure unit tests on the restoration logic ------------------------------

def test_reworded_restores_trailing_ellipsis():
    before = "te laisser semer la destruction\""
    after = "te laisser semer la destruction"
    living = "te laisser semer la destruction"  # re-worded copy, same tail
    assert mod._restore_reworded(before, after, living) == \
        f"te laisser semer la destruction{B0}"


def test_reworded_restores_multiple_sites():
    before = 'Argh"<0xFC><0x08><0x18> si seulement connaissait Tunnel"'
    after = 'Argh<0xFC><0x08><0x18> si seulement connaissait Tunnel'
    living = 'Argh<0xFC><0x08><0x18> si seulement connaissait Tunnel'
    assert mod._restore_reworded(before, after, living) == \
        f'Argh{B0}<0xFC><0x08><0x18> si seulement connaissait Tunnel{B0}'


def test_reworded_upgrades_legacy_ellipsis():
    """A site already restored to the 3-byte '…' is upgraded to the 0xB0 glyph."""
    before = "semer la destruction\""
    after = "semer la destruction"
    legacy = "semer la destruction…"  # earlier restoration form
    assert mod._restore_reworded(before, after, legacy) == \
        f"semer la destruction{B0}"


def test_reworded_is_idempotent():
    before = "semer la destruction\""
    after = "semer la destruction"
    once = mod._restore_reworded(before, after, "semer la destruction")
    twice = mod._restore_reworded(before, after, once)
    assert once == twice == f"semer la destruction{B0}"


def test_runs_collapse_to_single_glyph():
    # English "Toi………" (5 ellipsis bytes) → one pause beat, one byte.
    assert mod._to_ellipsis('Toi"""""') == f"Toi{B0}"


# --- guard: combined_fr.txt is fully restored, no lone ex-ellipsis quotes ---

def test_no_lone_ellipsis_quotes_remain():
    """Every offset R-09 stripped must now carry the 0xB0 glyph, not the
    deleted form and not a residual lone quote."""
    pairs = mod.load_r09_pairs()
    bodies = {}
    for line in COMBINED.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        off, rest = line.split(":", 1)
        off = off.strip().lower()
        if off.startswith("0x"):
            bodies[off] = rest.rstrip("\n")  # last duplicate wins

    missing = []
    for off, (before, after) in pairs.items():
        body = bodies.get(off)
        if body is None:
            continue
        want = mod._to_ellipsis(before)
        # Still in the deleted (lone-quote-able) state — pause never restored.
        if body == after and after != want:
            missing.append(off)
    assert missing == [], f"ellipsis pauses still deleted at: {missing[:10]}"


def test_known_entries_have_ellipsis_glyph():
    bodies = {}
    for line in COMBINED.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        off, rest = line.split(":", 1)
        bodies[off.strip().lower()] = rest
    # "perdu" pause, "Ce Pokémon" pause, and the Euh…go…Floe… hesitation,
    # all carrying the 1-byte 0xB0 glyph, no residual straight quote.
    assert f"perdu{B0}" in bodies["0x4577bc"]
    assert f"Ce Pokémon{B0}" in bodies["0x4586a0"]
    assert f"Euh{B0}go{B0}Floe{B0}" in bodies["0x7f165e"]


def test_rival_snooping_line_has_ellipsis_not_lone_quote():
    """0x1F2D412 (« Bref… tu vois, ils détestent… ») lived in the CSV/JSON only
    — not in combined_fr — so R-09 never reached it and its ex-ellipsis rendered
    as a lone quote in-game. It is now carried by combined_fr with the 0xB0
    glyph (1 byte, fits the 130-byte slot in place).
    """
    bodies = {}
    for line in COMBINED.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        off, rest = line.split(":", 1)
        bodies[off.strip().lower()] = rest  # last duplicate wins
    body = bodies["0x1f2d412"]
    assert f"Bref{B0}" in body, "ellipsis pause missing after « Bref »"
    assert 'Bref"' not in body, "lone quote still present after « Bref »"


def test_re_apply_changes_nothing():
    """Running the restorer again must restore zero entries (idempotent)."""
    assert mod.run(apply=False) == 0
