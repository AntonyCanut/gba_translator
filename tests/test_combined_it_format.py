"""Regression tests for the Italian combined-file format.

``combined_it.txt`` was generated from a JSON dump whose ``translated`` values
contained *real* newline characters, so multi-line strings spilled across
several physical lines. The build parser (``apply_combined_fr.py``) only treats
a line as an entry when it matches ``0x<offset>: <text>`` and silently drops
every other non-comment line — so each multi-line string was truncated to its
first line in the built ROM (the visible symptom being the incomplete game
intro). EN/FR/DE keep one entry per physical line with line breaks written as
the literal escape ``\\n``.

These tests pin the file to that canonical single-line format and guard the
generator so the bug cannot come back.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
COMBINED_IT = REPO_ROOT / "languages/it/combined_it.txt"
OFFSET_RE = re.compile(r"^\s*0x([0-9A-Fa-f]+)\s*:")


def _load_module(rel_path: str):
    path = REPO_ROOT / rel_path
    spec = importlib.util.spec_from_file_location(path.stem.lstrip("0123456789_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def parser():
    return _load_module("scripts/apply_combined_fr.py")


def test_combined_it_has_no_dropped_continuation_lines():
    """Every non-blank, non-comment line must be a parseable entry line.

    A line that is neither blank, a ``#`` comment, nor ``0x<offset>: ...`` is a
    continuation line the build silently drops — exactly the regression we fix.
    """
    orphans = []
    for lineno, raw in enumerate(COMBINED_IT.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if not OFFSET_RE.match(raw):
            orphans.append((lineno, raw[:60]))
    assert not orphans, (
        f"{len(orphans)} continuation line(s) would be dropped by the build parser; "
        f"first few: {orphans[:5]}"
    )


def test_intro_entries_are_complete(parser):
    """The intro segments must round-trip to their full multi-line text."""
    mapping, _ = parser._load_combined(COMBINED_IT)

    # Boot disclaimer (fullscreen) — must reach its last word, not stop after line 1.
    disclaimer = mapping[0x1F0F5A6]
    assert disclaimer.startswith("Benvenuto in Pokémon Unbound!")
    assert disclaimer.rstrip().endswith("rimborso!")
    assert "\n" in disclaimer  # line breaks are preserved for the fullscreen box

    # "Speak to people…" intro segment.
    speak = mapping[0x1F0F6FA]
    assert speak.startswith("Parla con le persone e controlla")
    assert speak.rstrip().endswith("cresceranno insieme a te.")

    # In-world narration variant (different offset, same incompleteness bug).
    world = mapping[0x1C5A04]
    assert world.startswith("Nel mondo in cui stai per entrare,")
    assert world.rstrip().endswith("con te come eroe.")


def test_generator_escapes_real_newlines():
    """The JSON→combined generator must emit literal ``\\n``, never raw newlines."""
    gen = _load_module("scripts/process_italian_translations.py")
    out = gen.escape_text("first line\nsecond line\n\nlast")
    assert "\n" not in out
    assert out == "first line\\nsecond line\\n\\nlast"
    # Already-escaped values must be left untouched (idempotent).
    assert gen.escape_text("already\\nescaped") == "already\\nescaped"


RAW_HEX_TOKEN_RE = re.compile(r"\{[0-9A-Fa-f]{2}\}")


def test_combined_it_has_no_raw_hex_tokens():
    """No ``{XX}`` raw-byte tokens may survive in the source.

    The JSON dump left bytes it could not map as ``{XX}`` literals (e.g. ``{B4}``
    for the apostrophe). The encoder does not understand them: it renders ``?B4?``
    in-game and inflates every apostrophe by 3 bytes, overflowing string slots and
    freezing the intro. They must be decoded to their CFRU character at import.
    """
    offenders = []
    for lineno, raw in enumerate(COMBINED_IT.read_text(encoding="utf-8").splitlines(), 1):
        # Skip the offset prefix; tokens only matter inside the translated text.
        text = raw.split(":", 1)[1] if ":" in raw else raw
        for m in RAW_HEX_TOKEN_RE.finditer(text):
            offenders.append((lineno, m.group(0)))
    assert not offenders, (
        f"{len(offenders)} raw {{XX}} hex token(s) left in combined_it.txt; "
        f"first few: {offenders[:8]}"
    )


def test_generator_decodes_hex_tokens():
    """The JSON→combined generator must decode ``{XX}`` tokens to characters."""
    gen = _load_module("scripts/process_italian_translations.py")
    # Apostrophe and Run/Fight menu letters that previously leaked as garbage.
    assert gen.decode_hex_tokens("c{B4}è fretta") == "c'è fretta"
    assert gen.decode_hex_tokens("{C0}uggi") == "Fuggi"
    assert gen.decode_hex_tokens("{A5}.000 GETTONI") == "4.000 GETTONI"
    # escape_text applies the decode as part of normalization.
    assert "{B4}" not in gen.escape_text("l{B4}aiuto")
    # Idempotent: a clean string is unchanged.
    assert gen.decode_hex_tokens("nessun token") == "nessun token"


def test_normalizer_is_idempotent_and_lossless():
    """Re-normalizing the (already single-line) file folds nothing."""
    norm = _load_module("scripts/normalize_combined_multiline.py")
    lines = COMBINED_IT.read_text(encoding="utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    _, joined = norm.normalize_lines(lines)
    assert joined == 0, "combined_it.txt still contains multi-line entries"
