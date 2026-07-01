"""Guard test: every Indie seed must be encodable by the CFRU charmap.

Indie reuses the French (Latin-only) font, so any character outside the
charmap silently falls back to ``POKEMON_TABLE['?']`` (``0xAC``) inside
``TextEncoder.encode_pokemon`` — the build does not raise, it just ships
rows of ``?``. This happened when the seeds were authored in Devanagari
(PR #1 review thread). This test fails loudly if any seed contains a
character that encodes to the ``?`` fallback.

Runs without any ROM or emulator.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.text_codec import TextEncoder

REPO_ROOT = Path(__file__).resolve().parents[1]
COMBINED_INDIE = REPO_ROOT / "languages" / "indie" / "combined_indie.txt"

FALLBACK_BYTE = 0xAC  # POKEMON_TABLE['?']


def _iter_seed_entries():
    """Yield (offset, text) for each non-comment entry in combined_indie.txt."""
    for raw in COMBINED_INDIE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        offset, _, text = line.partition(":")
        yield offset.strip(), text.strip()


def test_combined_indie_exists():
    assert COMBINED_INDIE.exists(), f"missing seed file: {COMBINED_INDIE}"


def test_indie_has_seed_entries():
    entries = list(_iter_seed_entries())
    assert entries, "combined_indie.txt has no seed entries to validate"


@pytest.mark.parametrize("offset,text", list(_iter_seed_entries()))
def test_indie_seed_encodes_without_fallback(offset, text):
    """No seed may contain a char the Latin charmap maps to the '?' fallback."""
    # A literal '?' in the source is legitimate; anything else that produces
    # 0xAC is an unencodable character (e.g. Devanagari) — reject it.
    encoded = TextEncoder.encode_pokemon(text)
    fallback_count = encoded.count(FALLBACK_BYTE)
    literal_question_marks = text.count("?")
    assert fallback_count <= literal_question_marks, (
        f"seed {offset} ({text!r}) has {fallback_count} '?' fallback byte(s) "
        f"but only {literal_question_marks} literal '?' — it contains "
        f"characters the Indie (French) font cannot encode."
    )
