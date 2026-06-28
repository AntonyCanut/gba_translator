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


# ── Control-token (colour / buffer / name) normalization ────────────────────

# Bracket/brace control tokens from the Italian dump. The encoder has no glyph
# for ``[`` / ``]`` / ``{`` / ``}``, so any survivor renders as ``?green?`` etc.
CONTROL_TOKEN_RE = re.compile(
    r"\[(?:green|red|blue|black|lightgreen|orange|darknavyblue"
    r"|buffer[123]|rival|pause)\]|\{player\}"
)


def test_combined_it_has_no_bracket_control_tokens():
    """No ``[green]`` / ``[buffer1]`` / ``{player}`` tokens may survive.

    These are colour codes (FC 01 NN), string buffers (FD NN) and name
    placeholders the dump wrote in its own readable convention. Left untouched
    the encoder spells them out as ``?green??buffer1??black?`` in-game (the
    reported bug). They must be converted to raw ``<0xNN>`` control codes.
    """
    offenders = []
    for lineno, raw in enumerate(COMBINED_IT.read_text(encoding="utf-8").splitlines(), 1):
        if raw.lstrip().startswith("#"):
            continue
        text = raw.split(":", 1)[1] if ":" in raw else raw
        for m in CONTROL_TOKEN_RE.finditer(text):
            offenders.append((lineno, m.group(0)))
    assert not offenders, (
        f"{len(offenders)} literal control token(s) left in combined_it.txt; "
        f"first few: {offenders[:8]}"
    )


def test_normalize_control_tokens_mappings():
    """Each token maps to its exact CFRU control sequence (verified vs EN ROM)."""
    gen = _load_module("scripts/process_italian_translations.py")
    n = gen.normalize_control_tokens
    # Colours → FC 01 NN
    assert n("[green]") == "<0xFC><0x01><0x06>"
    assert n("[red]") == "<0xFC><0x01><0x04>"
    assert n("[blue]") == "<0xFC><0x01><0x08>"
    assert n("[black]") == "<0xFC><0x01><0x02>"
    assert n("[lightgreen]") == "<0xFC><0x01><0x07>"
    assert n("[orange]") == "<0xFC><0x01><0x05>"
    assert n("[darknavyblue]") == "<0xFC><0x01><0x0F>"
    # Buffers / names → FD NN
    assert n("[buffer1]") == "<0xFD><0x02>"
    assert n("[buffer2]") == "<0xFD><0x03>"
    assert n("[buffer3]") == "<0xFD><0x04>"
    assert n("[rival]") == "<0xFD><0x06>"
    assert n("{player}") == "<0xFD><0x01>"
    # Flow control
    assert n("[pause]") == "<0xFC><0x09>"


def test_normalize_control_tokens_in_context():
    """The exact difficulty string from the bug report converts byte-for-byte.

    English raw at 0x1F10323 is ``…su <FC0106><FD02><FC0102>.`` (green buffer1
    black) — the Italian must produce the identical control bytes.
    """
    gen = _load_module("scripts/process_italian_translations.py")
    out = gen.normalize_control_tokens("impostata su [green][buffer1][black].")
    assert out == "impostata su <0xFC><0x01><0x06><0xFD><0x02><0xFC><0x01><0x02>."
    # A coloured word keeps its letters intact (no glyph eaten).
    assert gen.normalize_control_tokens("di [green]Pozioni[blue].") == (
        "di <0xFC><0x01><0x06>Pozioni<0xFC><0x01><0x08>."
    )


def test_normalize_control_tokens_leaves_plain_brackets():
    """Square brackets that are not known tokens must be left untouched."""
    gen = _load_module("scripts/process_italian_translations.py")
    assert gen.normalize_control_tokens("vedi [nota] e {altro}") == "vedi [nota] e {altro}"
    # Idempotent on already-raw text.
    assert gen.normalize_control_tokens("<0xFC><0x01><0x06>") == "<0xFC><0x01><0x06>"


def test_escape_text_applies_control_normalization():
    """escape_text normalizes control tokens as part of import."""
    gen = _load_module("scripts/process_italian_translations.py")
    out = gen.escape_text("Ciao {player}!\nUsa [green]Pozioni[black].")
    assert "{player}" not in out and "[green]" not in out
    assert out == "Ciao <0xFD><0x01>!\\nUsa <0xFC><0x01><0x06>Pozioni<0xFC><0x01><0x02>."


# ── Sound-macro normalization ─────────────────────────────────────────────────


def test_sound_macros_in_control_token_map():
    """[pause_music]/[wait_sound]/[resume_music] must map to verified FC bytes.

    Verified byte-for-byte from EN ROM at 0x1ee09a8 (Classic Leaders Gauntlet):
    the sequence after «Bravo!» is FC 17 / FC 0B 0C 01 / FC 0A / FC 18.
    """
    gen = _load_module("scripts/process_italian_translations.py")
    n = gen.normalize_control_tokens
    assert n("[pause_music]") == "<0xFC><0x17>"
    assert n("[wait_sound]") == "<0xFC><0x0A>"
    assert n("[resume_music]") == "<0xFC><0x18>"


def test_gauntlet_string_converts_byte_for_byte():
    """The Gauntlet completion string (0x1ee09a8) converts to exact ROM bytes.

    EN ROM after «Bravo!»: FC 17 FC 0B 0C 01 FC 0A FC 18
    IT dump: [pause_music]\\CC0B0C01[wait_sound][resume_music]
    """
    gen = _load_module("scripts/process_italian_translations.py")
    fragment = "Bravo![pause_music]\\CC0B0C01[wait_sound][resume_music] Per il tuo"
    # Apply the full escape_text pipeline (single backslash before CC)
    out = gen.escape_text(fragment)
    assert "[pause_music]" not in out
    assert "[wait_sound]" not in out
    assert "[resume_music]" not in out
    assert "\\CC" not in out
    assert out == (
        "Bravo!"
        "<0xFC><0x17>"
        "<0xFC><0x0B><0x0C><0x01>"
        "<0xFC><0x0A>"
        "<0xFC><0x18>"
        " Per il tuo"
    )


# ── Backslash-hex normalization ───────────────────────────────────────────────

# Regex that must match ZERO times in the normalized file: any residual \CC or
# \\XX (double-backslash + hex) that the pipeline cannot encode.
_RESIDUAL_CC_RE = re.compile(r"\\CC[0-9A-Fa-f]")
_RESIDUAL_DOUBLE_HEX_RE = re.compile(r"\\\\[0-9A-Fa-f]{2}")


def test_combined_it_has_no_cc_escape_tokens():
    r"""No ``\CC`` control-code escape sequences may survive in the file.

    The dump used ``\CCxxyy`` as a shorthand for FC-prefixed control sequences.
    Left untouched, the backslash renders as ``?CC0820?`` in-game.
    The importer must expand them to ``<0xFC><0xXX><0xYY>`` raw form.
    """
    offenders = []
    for lineno, raw in enumerate(COMBINED_IT.read_text(encoding="utf-8").splitlines(), 1):
        if raw.lstrip().startswith("#"):
            continue
        text = raw.split(":", 1)[1] if ":" in raw else raw
        if _RESIDUAL_CC_RE.search(text):
            offenders.append((lineno, text[:60]))
    assert not offenders, (
        f"{len(offenders)} residual \\CC token(s) left in combined_it.txt; "
        f"first few: {offenders[:5]}"
    )


def test_combined_it_has_no_double_backslash_hex_tokens():
    r"""No ``\\07``–``\\0C`` double-backslash FD-buffer tokens may survive.

    The dump wrote FD-buffer placeholders as ``\\07``…``\\0C`` (double backslash).
    The encoder does not understand them; they render as garbage in-game.
    """
    offenders = []
    for lineno, raw in enumerate(COMBINED_IT.read_text(encoding="utf-8").splitlines(), 1):
        if raw.lstrip().startswith("#"):
            continue
        text = raw.split(":", 1)[1] if ":" in raw else raw
        if _RESIDUAL_DOUBLE_HEX_RE.search(text):
            offenders.append((lineno, text[:60]))
    assert not offenders, (
        f"{len(offenders)} residual double-backslash hex token(s) in combined_it.txt; "
        f"first few: {offenders[:5]}"
    )


def test_normalize_backslash_cc_escapes():
    r"""``\CC<hex_pairs>`` must expand to ``<0xFC>`` + per-pair bytes.

    Verified against EN ROM:
    - ``\CC0820`` → FC 08 20 (timed pause 32 frames)
    - ``\CC0818`` → FC 08 18 (timed pause 24 frames)
    - ``\CC0B0C01`` → FC 0B 0C 01 (play SE with song ID 0x0C01)
    - ``\CC040D0E0F`` → FC 04 0D 0E 0F (4 argument bytes)
    Trailing odd digit is NOT consumed: ``\CC06001,000`` → ``<0xFC><0x06><0x00>1,000``.
    """
    gen = _load_module("scripts/process_italian_translations.py")
    n = gen.normalize_backslash_escapes
    assert n("\\CC0820") == "<0xFC><0x08><0x20>"
    assert n("\\CC0818") == "<0xFC><0x08><0x18>"
    assert n("\\CC0B0C01") == "<0xFC><0x0B><0x0C><0x01>"
    assert n("\\CC040D0E0F") == "<0xFC><0x04><0x0D><0x0E><0x0F>"
    # Trailing odd digit is text, not part of the escape
    assert n("\\CC06001,000") == "<0xFC><0x06><0x00>1,000"
    # Embedded in sentence
    assert n("parola.\\CC0820 Fine.") == "parola.<0xFC><0x08><0x20> Fine."
    # Idempotent
    assert n("<0xFC><0x08><0x20>") == "<0xFC><0x08><0x20>"


def test_normalize_backslash_fd_buffer_tokens():
    r"""Double-backslash ``\\07``–``\\0C`` must decode to ``<0xFD><0xNN>``.

    These are FD string-buffer placeholders verified byte-for-byte from EN ROM:
    - ``\\07`` → FD 07 (buffer 7: player age, item counts, …)
    - ``\\08`` → FD 08 (buffer 8: Frontier example count)
    - ``\\0C`` → FD 0C (buffer 12: Lucky Egg multiplier)
    The double backslash is the file convention (the original import stored the
    raw ``\\07`` from JSON without decoding it).
    """
    gen = _load_module("scripts/process_italian_translations.py")
    n = gen.normalize_backslash_escapes
    # Double-backslash tokens (as they appear in the file)
    assert n("hai \\\\07 anni!") == "hai <0xFD><0x07> anni!"
    assert n("[green]\\\\07[red]") == "[green]<0xFD><0x07>[red]"
    assert n("\\\\08 esempi") == "<0xFD><0x08> esempi"
    assert n("\\\\0C volte") == "<0xFD><0x0C> volte"
    # Case-insensitive hex digits
    assert n("\\\\0c volte") == "<0xFD><0x0C> volte"
    # Already-converted form is left alone
    assert n("<0xFD><0x07>") == "<0xFD><0x07>"


def test_normalize_backslash_navigation_tokens():
    r"""Single-backslash navigation tokens must decode to their raw arrow bytes.

    Verified against EN ROM route descriptions:
    - ``\au`` → 0x79 (↑)   ``\ad`` → 0x7A (↓)
    - ``\al`` → 0x7B (←)   ``\ar`` → 0x7C (→)
    - ``\qo`` → 0xB1 (")   ``\qc`` → 0xB2 (")
    """
    gen = _load_module("scripts/process_italian_translations.py")
    n = gen.normalize_backslash_escapes
    assert n("\\au Frozen Heights \\ad Bellin Town") == (
        "<0x79> Frozen Heights <0x7A> Bellin Town"
    )
    assert n("\\al Grim Woods \\ar Dresco Town \\ad Percorso 13") == (
        "<0x7B> Grim Woods <0x7C> Dresco Town <0x7A> Percorso 13"
    )
    assert n("\\qoPercorso 1\\qc") == "<0xB1>Percorso 1<0xB2>"


def test_escape_text_applies_backslash_normalization():
    r"""escape_text must normalize backslash-hex tokens as part of import."""
    gen = _load_module("scripts/process_italian_translations.py")
    # CC escape in a real sentence
    out = gen.escape_text("fine.\\CC0820 Poi")
    assert "\\CC" not in out
    assert out == "fine.<0xFC><0x08><0x20> Poi"
    # Double-backslash FD buffer in a real sentence
    out = gen.escape_text("hai \\\\07 anni!")
    assert "\\\\07" not in out
    assert out == "hai <0xFD><0x07> anni!"
