"""Regression tests for the wordless-quote cleanup (ticket R-09 follow-up).

byte 0xB0 (the ellipsis glyph) was decoded into the FR source as a straight
double quote.  After the encoder fix those quotes render as stray quote glyphs
with nothing inside them; they must be removed while genuine quotations (English
0xB1/0xB2) are kept.  See scripts/clean_wordless_quotes_fr.py.
"""

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "clean_wordless_quotes_fr.py"
COMBINED = REPO / "combined_fr.txt"
ENGLISH_ROM = REPO / "input" / "roms" / "englishrom.gba"

spec = importlib.util.spec_from_file_location("clean_wordless_quotes_fr", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# --- pure unit tests on the string transform -------------------------------

def test_word_between_quotes_becomes_space():
    # stray quotes between two words must not glue them together
    assert mod.strip_quotes('Euh"go"Floe"') == "Euh go Floe"


def test_runs_of_quotes_removed():
    assert mod.strip_quotes('Toi""""\\pMeurs"""') == "Toi\\pMeurs"


def test_trailing_quote_removed():
    assert mod.strip_quotes("SANS FIL a été perdu\"") == "SANS FIL a été perdu"
    assert mod.strip_quotes('Ce Pokémon"') == "Ce Pokémon"


def test_quote_before_space_collapses():
    assert mod.strip_quotes('Sinon" dis-moi') == "Sinon dis-moi"


def test_quote_before_control_code_kept_clean():
    assert (
        mod.strip_quotes('Allez"<0xFC><0x08><0x10> ouvre-toi"<0xFC><0x08><0x30>')
        == "Allez<0xFC><0x08><0x10> ouvre-toi<0xFC><0x08><0x30>"
    )


def test_no_space_before_linebreak_escape():
    assert mod.strip_quotes('mot " \\nsuite') == "mot\\nsuite"


# --- ground-truth classification -------------------------------------------

@pytest.mark.skipif(not ENGLISH_ROM.is_file(), reason="english ROM not available")
def test_ellipsis_origin_entries_classified_remove():
    import src.core.text_codec as tc

    dec = tc.TextDecoder()
    rom = ENGLISH_ROM.read_bytes()
    # English used the ellipsis glyph here, no real quotes -> remove
    for off in ("0x4577bc", "0x8cd194", "0x7f3707"):
        assert mod.classify(dec, rom, off) == "remove"
    # English used genuine curly quotes here -> keep
    for off in ("0x7804f5", "0x7b8a54", "0xeb201d"):
        assert mod.classify(dec, rom, off) == "keep"


# --- guard: the source file is fully cleaned -------------------------------

@pytest.mark.skipif(not ENGLISH_ROM.is_file(), reason="english ROM not available")
def test_combined_fr_has_no_residual_wordless_quotes():
    """Re-running the cleaner over combined_fr.txt must change nothing."""
    import src.core.text_codec as tc

    dec = tc.TextDecoder()
    rom = ENGLISH_ROM.read_bytes()
    residual = []
    for line in COMBINED.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        off, rest = line.split(":", 1)
        off = off.strip()
        if '"' not in rest:
            continue
        if mod.classify(dec, rom, off) != "remove":
            continue  # genuine quotation, intentionally kept
        if mod.strip_quotes(rest) != rest:
            residual.append(off)
    assert residual == [], f"wordless quotes still present at: {residual[:10]}"


def test_genuine_quotations_are_preserved():
    """Real quotations must still carry their straight quotes in the source."""
    text = COMBINED.read_text(encoding="utf-8")
    lines = {ln.split(":", 1)[0].strip(): ln for ln in text.splitlines() if ":" in ln}
    for off in ("0x7804F5", "0x7B8A54", "0xEB201D", "0x7768A4"):
        assert '"' in lines[off], f"genuine quotation lost at {off}"
