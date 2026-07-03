"""Tests for scripts/patch_pokedex_de.py and the German-glyph charset fix in
src/core/pokedex.py (``_ALLOWED`` must accept ä ö ü Ä Ö Ü ß, or every German
Pokédex description would be rejected by ``is_description``/rewritten as
"not a description" and left English).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.core import pokedex  # noqa: E402
import patch_pokedex_de as mod  # noqa: E402


class TestGermanCharsetAccepted:
    def test_is_description_accepts_umlauts(self):
        text = "Ein wütender Käfer mit übergroßen Fühlern."
        assert pokedex.is_description(text)

    def test_fits_accepts_umlauts(self):
        text = "Es späht über Bäume und Flüsse."
        assert pokedex.fits(text)

    def test_rewrap_roundtrips_umlaut_text(self):
        text = "Dieses Pokémon liebt süße Früchte und schläft gerne in der Höhle."
        wrapped = pokedex.rewrap(text)
        assert wrapped.replace("\n", " ") == text


class TestApplyIsGenericDelegate:
    def test_apply_and_load_text_map_are_importable(self):
        # patch_pokedex_de.py must not carry any FR-specific baked strings —
        # it is a thin language-agnostic delegate, mirroring patch_pokedex_fr.py.
        assert callable(mod.apply)
        assert callable(mod.load_text_map)
        assert mod.DEFAULT_OVERRIDES.name == "pokedex_de_overrides.json"
        assert "de" in str(mod.DEFAULT_OVERRIDES)
