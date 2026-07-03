"""E2E: Pokédex struct-table offsets actually carry Italian text.

`patch_pokedex_it.py`'s ``text_map`` (keyed by the generic pipeline's
extraction offset) coincides with a live Pokédex-struct ``text_offset``
for only a handful of entries, and its curated-override fallback
(``languages/it/data/pokedex_it_overrides.json``) used to not exist on
disk — so almost every description silently fell back to the source
ROM's text, which is itself untranslated French left over from the
FR-first build layout (see B-164). This asserts a known, previously
broken entry (Bulbasaur, dex-struct index 1) now decodes to genuine
Italian in the built ROM instead of French.
"""

from __future__ import annotations

import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from src.core import pokedex  # noqa: E402
from src.core.text_codec import TextDecoder  # noqa: E402


def _resolve_project_root() -> pathlib.Path:
    env_root = os.environ.get("GBA_PROJECT_ROOT")
    if env_root:
        return pathlib.Path(env_root)
    return pathlib.Path(__file__).resolve().parent.parent.parent.parent


PROJECT_ROOT = _resolve_project_root()
IT_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-it.gba"
EN_ROM_PATH = PROJECT_ROOT / "input" / "roms" / "englishrom.gba"

ROM_POINTER_BASE = 0x08000000

# The exact French leftover previously shipped at this offset (Bulbasaur,
# dex-struct index 1) — verified byte-identical to englishrom.gba before
# the fix. Used to prove the built ROM no longer contains it.
_FRENCH_LEFTOVER_MARKERS = ("Lorsque", "célébrer")


def _deref(data: bytes, offset: int) -> int | None:
    value = int.from_bytes(data[offset:offset + 4], "little")
    if ROM_POINTER_BASE <= value < ROM_POINTER_BASE + 0x02000000:
        return value - ROM_POINTER_BASE
    return None


@pytest.fixture(scope="module")
def en_rom_data():
    if not EN_ROM_PATH.exists():
        pytest.skip("englishrom.gba not found in input/roms/")
    return EN_ROM_PATH.read_bytes()


@pytest.fixture(scope="module")
def it_rom_data():
    if not IT_ROM_PATH.exists():
        pytest.skip(
            "GenedRom-it.gba not found — run: python3 scripts/build_language.py it"
        )
    return IT_ROM_PATH.read_bytes()


class TestKnownUncoveredBuckets:
    def test_bulbasaur_dex_description_is_italian(self, en_rom_data, it_rom_data):
        entry = next(e for e in pokedex.iter_entries(en_rom_data) if e.index == 1)

        target = _deref(it_rom_data, entry.struct_offset)
        assert target is not None, "Bulbasaur dex-struct pointer is unreadable"

        end = it_rom_data.find(b"\xff", target)
        text = TextDecoder.decode_pokemon(it_rom_data[target:end], preserve_unknown=True)

        for marker in _FRENCH_LEFTOVER_MARKERS:
            assert marker not in text, (
                f"Bulbasaur Pokédex description still contains French leftover "
                f"text ({marker!r}): {text!r}"
            )
        # Distinctive Italian function words that appear in the curated
        # override, absent from the French source.
        assert "il" in text.lower() and "per" in text.lower()
