"""Regression tests for ellipsis-pause restoration (ticket R-09 follow-up #2).

R-09 *deleted* the ex-ellipsis quote glyphs (English byte 0xB0 = "…") that had
been decoded into combined_fr.txt as straight double quotes. Deletion threw away
the intended pause ("Bref" tu vois" → "Bref tu vois" instead of "Bref… tu
vois"). This restores them as "…". See scripts/restore_ellipsis_pauses_fr.py.
"""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "restore_ellipsis_pauses_fr.py"
COMBINED = REPO / "combined_fr.txt"

spec = importlib.util.spec_from_file_location("restore_ellipsis_pauses_fr", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# --- pure unit tests on the restoration logic ------------------------------

def test_reworded_restores_trailing_ellipsis():
    before = "te laisser semer la destruction\""
    after = "te laisser semer la destruction"
    living = "te laisser semer la destruction"  # re-worded copy, same tail
    assert mod._restore_reworded(before, after, living) == \
        "te laisser semer la destruction…"


def test_reworded_restores_multiple_sites():
    before = 'Argh"<0xFC><0x08><0x18> si seulement connaissait Tunnel"'
    after = 'Argh<0xFC><0x08><0x18> si seulement connaissait Tunnel'
    living = 'Argh<0xFC><0x08><0x18> si seulement connaissait Tunnel'
    assert mod._restore_reworded(before, after, living) == \
        'Argh…<0xFC><0x08><0x18> si seulement connaissait Tunnel…'


def test_reworded_is_idempotent():
    before = "semer la destruction\""
    after = "semer la destruction"
    once = mod._restore_reworded(before, after, "semer la destruction")
    twice = mod._restore_reworded(before, after, once)
    assert once == twice == "semer la destruction…"


# --- guard: combined_fr.txt is fully restored, no lone ex-ellipsis quotes ---

def test_no_lone_ellipsis_quotes_remain():
    """Every offset R-09 stripped must now carry "…", not the deleted form."""
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
        # the R-09 "deleted" form must no longer be the living text
        if body == after and after != before.replace('"', '…'):
            missing.append(off)
    assert missing == [], f"ellipsis pauses still deleted at: {missing[:10]}"


def test_known_entries_have_ellipsis():
    bodies = {}
    for line in COMBINED.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        off, rest = line.split(":", 1)
        bodies[off.strip().lower()] = rest
    # "perdu" pause, "Ce Pokémon" pause, and the Euh…go…Floe… hesitation
    assert "perdu…" in bodies["0x4577bc"]
    assert "Ce Pokémon…" in bodies["0x4586a0"]
    assert "Euh…go…Floe…" in bodies["0x7f165e"]


def test_re_apply_changes_nothing():
    """Running the restorer again must restore zero entries (idempotent)."""
    assert mod.run(apply=False) == 0
