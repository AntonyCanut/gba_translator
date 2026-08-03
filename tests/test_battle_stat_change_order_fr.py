"""Regression guard for the battle stat-change effect messages (ticket B-35).

In battle, the "{Pokémon}'s {Stat} rose/fell!" templates must read in correct,
idiomatic French. Two things are pinned here:

1. Word order of the noun phrase: "[STAT] de [NOM]" (e.g. "Défense de Pikachu"),
   NOT the inverted "[NOM] de [STAT]".
2. Placement of the intensity adverb. The engine builds the verb buffer
   (<0xFD><0x01>) as ``[modifier?] + [verb]`` and the modifier is ALWAYS
   prepended (English "sharply rose!"). Authoring the verb as "augmente !" and
   the modifier as "beaucoup " therefore produced "beaucoup augmente !" — wrong
   French order ("la phrase manque de sens").

   The fix moves the conjugated verb INTO the templates and shrinks the verb
   buffer to just "!". With the verb fixed in the template, the prepended
   modifier now lands *after* the verb:

       template (rise) = "<0xFD><0x00> de <0xFD><0x0F>\\naugmente <0xFD><0x01>"
       verb buffer     = "!"
       modifier        = "beaucoup "   (rise & fall)

       +1 : "Défense de Pikachu\\naugmente !"           (buffer = "!")
       +2 : "Défense de Pikachu\\naugmente beaucoup !"  (buffer = "beaucoup " + "!")
       -1 : "Défense de Pikachu\\nbaisse !"
       -2 : "Défense de Pikachu\\nbaisse beaucoup !"

Buffer mapping (verified against the EN ROM, FireRed STRINGID enum):

    <0xFD><0x00>  -> stat name buffer        (e.g. "Défense")
    <0xFD><0x0F>  -> attacker name buffer
    <0xFD><0x10>  -> defender name buffer
    <0xFD><0x01>  -> intensity+terminator buffer ("!" or "beaucoup !")

    0x3FCB5F / 0x3FCB6A  -> RISE templates (attacker / defender)  [STRINGID 0xC9/0xCA]
    0x3FCB8F / 0x3FCB9A  -> FALL templates (attacker / defender)  [STRINGID 0xCB/0xCC]
    0x3FCB41 / 0x3FCB50  -> modifier (rise / fall), "beaucoup "
    0x3FCB4A / 0x3FCB59  -> verb buffer (rise / fall), "!"
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.core.text_codec import TextDecoder, TextEncoder

COMBINED = Path(__file__).resolve().parent.parent / "languages/fr/combined_fr.txt"
FR_ROM = Path(__file__).resolve().parent.parent / "output/roms/GenedRom-fr.gba"

# rise-direction templates / fall-direction templates
RISE_TEMPLATES = (0x3FCB5F, 0x3FCB6A)
FALL_TEMPLATES = (0x3FCB8F, 0x3FCB9A)
ATK_TEMPLATES = (0x3FCB5F, 0x3FCB8F)
DEF_TEMPLATES = (0x3FCB6A, 0x3FCB9A)
MODIFIERS = (0x3FCB41, 0x3FCB50)
VERB_BUFFERS = (0x3FCB4A, 0x3FCB59)
ACCURACY_STAT_NAME = 0x3FD5B8
ACCURACY_POINTER_SITE = 0x3FD5E8
EVASION_STAT_NAME = 0x3FD5C1
EVASION_POINTER_SITE = 0x3FD5EC
GBA_ROM_BASE = 0x08000000


def _last_entries() -> dict[int, str]:
    """Parse combined_fr.txt; for duplicate offsets the LAST entry wins."""
    entries: dict[int, str] = {}
    line_re = re.compile(r"^0x([0-9A-Fa-f]+):\s?(.*)$")
    for raw in COMBINED.read_text(encoding="utf-8").splitlines():
        m = line_re.match(raw)
        if m:
            entries[int(m.group(1), 16)] = m.group(2)
    return entries


def _encode(text: str) -> bytes:
    # combined_fr.txt uses \n as the newline escape; the encoder maps it via
    # the control table, so feed a real newline.
    return TextEncoder.encode(text.replace("\\n", "\n"), "pokemon")


def _decode_buffer(text: str) -> str:
    """Render a combined_fr value to a plain string, resolving the explicit
    <0x00> space token, for assertions about the displayed text."""
    return text.replace("<0x00>", " ").replace("\\n", "\n")


def test_templates_use_control_byte_not_brace_syntax():
    """Brace tokens like {FD00} are NOT understood by the encoder and would be
    written as literal text. The templates must use <0xFD><0x..> syntax."""
    entries = _last_entries()
    for off in ATK_TEMPLATES + DEF_TEMPLATES:
        text = entries[off]
        assert "{FD" not in text, f"{off:#x} uses brace syntax (encodes as garbage): {text!r}"
        assert "<0xFD>" in text, f"{off:#x} missing control-byte tokens: {text!r}"


def test_accuracy_stat_name_starts_with_uppercase():
    """Le nom injecté dans le message de combat doit être « Précision »."""
    entries = _last_entries()

    assert entries[ACCURACY_STAT_NAME] == "Précision"


def test_evasion_stat_name_starts_with_uppercase():
    """Le nom injecté dans le message de combat doit être « Esquive »."""
    entries = _last_entries()

    assert entries[EVASION_STAT_NAME] == "Esquive"


@pytest.mark.rom
def test_built_rom_accuracy_pointer_renders_uppercase():
    """Le pointeur consommé en combat doit résoudre « Précision » dans la ROM."""
    rom = FR_ROM.read_bytes()
    pointer = int.from_bytes(rom[ACCURACY_POINTER_SITE : ACCURACY_POINTER_SITE + 4], "little")
    target = pointer - GBA_ROM_BASE
    end = rom.index(0xFF, target) + 1

    assert TextDecoder.decode_pokemon(rom[target:end]) == "Précision"


@pytest.mark.rom
def test_built_rom_evasion_pointer_renders_uppercase():
    """Le pointeur consommé en combat doit résoudre « Esquive » dans la ROM."""
    rom = FR_ROM.read_bytes()
    pointer = int.from_bytes(rom[EVASION_POINTER_SITE : EVASION_POINTER_SITE + 4], "little")
    target = pointer - GBA_ROM_BASE
    end = rom.index(0xFF, target) + 1

    assert TextDecoder.decode_pokemon(rom[target:end]) == "Esquive"


def test_stat_precedes_name_in_source():
    """French order: stat (<0xFD><0x00>) before name (<0xFD><0x0F>/<0x10>)."""
    entries = _last_entries()
    for off in ATK_TEMPLATES:
        text = entries[off]
        assert text.index("<0x00>") < text.index("<0x0F>"), (
            f"{off:#x} inverted — name before stat: {text!r}"
        )
    for off in DEF_TEMPLATES:
        text = entries[off]
        assert text.index("<0x00>") < text.index("<0x10>"), (
            f"{off:#x} inverted — name before stat: {text!r}"
        )


def test_encoded_byte_order_stat_then_de_then_name():
    """The encoded bytes must be FD 00 ... 'de' ... FD 0F (stat, de, name)."""
    entries = _last_entries()
    de = TextEncoder.encode("de", "pokemon")[:-1]  # drop terminator
    for off, name_byte in (
        (0x3FCB5F, 0x0F),
        (0x3FCB8F, 0x0F),
        (0x3FCB6A, 0x10),
        (0x3FCB9A, 0x10),
    ):
        enc = _encode(entries[off])
        i_stat = enc.find(b"\xfd\x00")
        i_de = enc.find(de)
        i_name = enc.find(bytes((0xFD, name_byte)))
        assert i_stat != -1 and i_de != -1 and i_name != -1, f"{off:#x}: {enc.hex()}"
        assert i_stat < i_de < i_name, (
            f"{off:#x} wrong order stat={i_stat} de={i_de} name={i_name}: {enc.hex()}"
        )


def test_verb_is_baked_into_template_before_buffer():
    """The conjugated verb must live in the template (after the name buffer,
    before the trailing <0xFD><0x01>), so the prepended modifier lands after it.

    Rise templates carry "augmente"; fall templates carry "baisse"."""
    entries = _last_entries()
    for off in RISE_TEMPLATES:
        text = entries[off]
        assert "augmente" in text, f"{off:#x} rise template lost verb: {text!r}"
        assert text.index("augmente") < text.index("<0x01>"), (
            f"{off:#x} verb must precede the intensity buffer: {text!r}"
        )
    for off in FALL_TEMPLATES:
        text = entries[off]
        assert "baisse" in text, f"{off:#x} fall template lost verb: {text!r}"
        assert text.index("baisse") < text.index("<0x01>"), (
            f"{off:#x} verb must precede the intensity buffer: {text!r}"
        )


def test_verb_buffer_is_only_the_exclamation():
    """With the verb in the template, the verb buffer must shrink to just "!"
    so ±1 renders "augmente !" and ±2 renders "augmente beaucoup !"."""
    entries = _last_entries()
    for off in VERB_BUFFERS:
        text = entries[off]
        assert _decode_buffer(text).strip() == "!", (
            f"{off:#x} verb buffer must be just '!': {text!r}"
        )


def test_modifier_keeps_trailing_space():
    """'beaucoup' must end with a space so it does not stick to the '!'.

    The trailing separator is authored as the explicit space byte token
    <0x00> (literal trailing spaces get trimmed by line-based tooling)."""
    entries = _last_entries()
    for off in MODIFIERS:
        text = entries[off]
        enc = _encode(text)[:-1]  # drop terminator
        assert enc.endswith(b"\x00"), f"{off:#x} modifier lost trailing space: {text!r}"


def test_rendered_order_is_verb_then_modifier():
    """End-to-end: simulate the engine (buffer = modifier + verb) and assert the
    +2 message reads "augmente beaucoup !" — verb first, intensity adverb after —
    NOT the old "beaucoup augmente !"."""
    entries = _last_entries()

    def render(template_off: int, modifier_off: int | None, verb_off: int) -> str:
        # Resolve buffer pieces (these carry the explicit <0x00> space token).
        verb_buf = _decode_buffer(entries[verb_off])
        modifier = _decode_buffer(entries[modifier_off]) if modifier_off else ""
        buff2 = modifier + verb_buf  # engine prepends the modifier
        # Substitute the FD control tokens on the RAW template first, then the
        # newline escape; the templates have no standalone <0x00> token.
        text = entries[template_off]
        text = text.replace("<0xFD><0x00>", "Défense")
        text = text.replace("<0xFD><0x0F>", "Pikachu").replace("<0xFD><0x10>", "Pikachu")
        text = text.replace("<0xFD><0x01>", buff2)
        return text.replace("\\n", "\n")

    # +1 / +2 rise
    assert render(0x3FCB5F, None, 0x3FCB4A) == "Défense de Pikachu\naugmente !"
    assert render(0x3FCB5F, 0x3FCB41, 0x3FCB4A) == "Défense de Pikachu\naugmente beaucoup !"
    # -1 / -2 fall
    assert render(0x3FCB9A, None, 0x3FCB59) == "Défense de Pikachu\nbaisse !"
    assert render(0x3FCB9A, 0x3FCB50, 0x3FCB59) == "Défense de Pikachu\nbaisse beaucoup !"

    # And the broken order must NOT appear.
    plus_two = render(0x3FCB5F, 0x3FCB41, 0x3FCB4A)
    assert plus_two.index("augmente") < plus_two.index("beaucoup"), (
        f"verb must precede the adverb: {plus_two!r}"
    )


def test_no_phantom_entry_after_rise_verb_buffer():
    """Regression guard (issue #26): a leftover, unreferenced English fragment
    ("ose!", a substring of the old "rose!" verb) once sat one byte past the
    rise verb buffer at 0x3FCB4A. It has zero pointer referrers in the English
    ROM — it is dead data that happens to be byte-adjacent to a live string —
    but combined_fr.txt still carried an entry for it at 0x3FCB4B. Because
    0x3FCB4A shrank to just "!" (see B-35 above), the injector wrote this
    phantom entry directly after the "!" terminator, corrupting the in-game
    message into "... augmente !ose !" instead of "... augmente !".

    There must be no combined_fr.txt entry for this dead offset."""
    entries = _last_entries()
    assert 0x3FCB4B not in entries, (
        "0x3FCB4B is a phantom, unreferenced offset one byte past the rise "
        "verb buffer (0x3FCB4A) — it must not be translated/present, or it "
        "corrupts the live '!' terminator into '!ose!' in-game."
    )
