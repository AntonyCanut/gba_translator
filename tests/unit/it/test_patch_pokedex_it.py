"""Tests for scripts/patch_pokedex_it.py and the Italian-glyph charset fix in
src/core/pokedex.py (``_ALLOWED`` must accept ì ò Ì Ò, or every Italian
Pokédex description using a grave-accented vowel would be rejected by
``is_description``/rewritten as "not a description" and left English).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.core import pokedex  # noqa: E402
from src.core.text_codec import TextDecoder, TextEncoder  # noqa: E402
import patch_pokedex_it as mod  # noqa: E402


def _ptr(offset: int) -> bytes:
    return (offset + mod.ROM_POINTER_BASE).to_bytes(4, "little")


def _decode(rom: bytes, offset: int) -> str:
    end = rom.find(b"\xff", offset)
    return TextDecoder.decode_pokemon(rom[offset:end], preserve_unknown=True)


class TestItalianCharsetAccepted:
    def test_is_description_accepts_grave_accents(self):
        text = "Un Pokémon curioso che ama esplorare la foresta più fitta."
        assert pokedex.is_description(text)

    def test_fits_accepts_grave_accents(self):
        text = "Osserva con attenzione ciò che lo circonda ogni giorno."
        assert pokedex.fits(text)

    def test_rewrap_roundtrips_grave_accent_text(self):
        text = "Questo Pokémon dorme così a lungo che sembra quasi immobile."
        wrapped = pokedex.rewrap(text)
        assert wrapped.replace("\n", " ") == text


class TestApplyIsGenericDelegate:
    def test_apply_and_load_text_map_are_importable(self):
        # patch_pokedex_it.py must not carry any Italian-specific baked
        # strings — it is a thin language-agnostic delegate, mirroring
        # patch_pokedex_fr.py / patch_pokedex_de.py.
        assert callable(mod.apply)
        assert callable(mod.load_text_map)
        assert mod.DEFAULT_OVERRIDES.name == "pokedex_it_overrides.json"
        assert "it" in str(mod.DEFAULT_OVERRIDES)


class TestWidthOverflowIsTolerated:
    """A description too dense for the reference line width must NOT fail the
    build (same regression class as B-158/B-159 for DE).

    ``rewrap`` guarantees <= 3 lines, so the entry always renders inside the
    box; the width overflow is written best-effort and merely tracked.
    """

    def setup_method(self):
        self._base, self._count = pokedex.DEX_TABLE_BASE, pokedex.DEX_TABLE_COUNT
        pokedex.DEX_TABLE_BASE = 0x100
        pokedex.DEX_TABLE_COUNT = 4

    def teardown_method(self):
        pokedex.DEX_TABLE_BASE, pokedex.DEX_TABLE_COUNT = self._base, self._count

    def test_overflow_description_is_written_not_failed(self):
        # Dense Italian text: fits <= 3 lines but a line exceeds DEX_LINE_WIDTH.
        dense = (
            "Questo audace Pokémon non teme di sfidare avversari molto più "
            "grandi di lui e vola instancabilmente alla ricerca di un clima "
            "caldo e accogliente."
        )
        assert not pokedex.fits(dense)  # precondition: genuinely over-width

        short_source = "Un piccolo Pokémon."
        src = bytearray(0x8000)
        rom = bytearray(0x8000)
        slot = 0x400
        for data in (src, rom):
            enc = TextEncoder.encode_pokemon(short_source)
            data[slot:slot + len(enc)] = enc
            data[0x100:0x104] = _ptr(slot)
        # free-space run so the longer rewrapped text can be relocated
        rom[0x2000:0x6000] = b"\xff" * 0x4000

        stats = mod.apply(rom, bytes(src), {slot: dense}, {})

        assert stats["failed"] == 0, "width overflow must never be a hard failure"
        assert stats["overflow"] == 1
        new_offset = int.from_bytes(rom[0x100:0x104], "little") - mod.ROM_POINTER_BASE
        result = _decode(rom, new_offset)
        assert result.count("\n") + 1 <= pokedex.DEX_MAX_LINES
        # Wording preserved verbatim (only line breaks change). Compare against
        # the codec round-trip so the EN-charmap unit encoder — which lacks the
        # IT grave-accent glyphs the font patch adds — does not confuse the check.
        roundtrip = TextDecoder.decode_pokemon(
            TextEncoder.encode_pokemon(dense), preserve_unknown=True
        )
        assert result.replace("\n", " ") == roundtrip

    def test_overflow_without_free_space_keeps_text_and_does_not_fail(self):
        # No free-space run available: the entry cannot be relocated, but the
        # build must still complete (skip in place, never fail).
        dense = (
            "Questo audace Pokémon non teme di sfidare avversari molto più "
            "grandi di lui e vola instancabilmente alla ricerca di un clima "
            "caldo e accogliente."
        )
        short_source = "Un piccolo Pokémon."
        src = bytearray(0x4000)
        rom = bytearray(0x4000)
        slot = 0x400
        for data in (src, rom):
            enc = TextEncoder.encode_pokemon(short_source)
            data[slot:slot + len(enc)] = enc
            data[0x100:0x104] = _ptr(slot)
        # no 0xFF free-space block → allocate() returns None

        stats = mod.apply(rom, bytes(src), {slot: dense}, {})

        assert stats["failed"] == 0
        assert stats["overflow"] == 1
        assert stats["skip_no_space"] == 1
