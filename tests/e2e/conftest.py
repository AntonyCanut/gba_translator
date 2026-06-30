"""E2E test fixtures for gba_translator.

Provides ROM paths, translation files, and shared test data
for end-to-end testing of the full translation pipeline.
"""

import pathlib

import pytest


def _resolve_project_root() -> pathlib.Path:
    """Return the project root the tests are actually running from.

    Defaults to the checkout containing this file — when running inside a
    git worktree (.singularity-worktrees/<id>/), that's the worktree's own
    checkout, so tests exercise the ROM that was built/checked out there
    instead of silently reading whatever the main checkout happens to have
    at that moment (which can be mid-edit from a concurrent task). Set
    GBA_PROJECT_ROOT to explicitly point at a different (e.g. shared/
    canonical) checkout.
    """
    import os
    env = os.environ.get("GBA_PROJECT_ROOT")
    if env:
        return pathlib.Path(env)
    return pathlib.Path(__file__).resolve().parent.parent.parent


PROJECT_ROOT = _resolve_project_root()

EN_ROM_PATH = PROJECT_ROOT / "input" / "roms" / "englishrom.gba"
ES_ROM_PATH = PROJECT_ROOT / "input" / "roms" / "spanishrom.gba"
FR_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-fr.gba"
IT_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-it.gba"

TRANSLATION_READY = PROJECT_ROOT / "output" / "translation" / "2026-01-16_translation_ready.json"
FRENCH_TEXTS = PROJECT_ROOT / "output" / "translation" / "french_texts.json"


@pytest.fixture
def en_rom_path():
    if not EN_ROM_PATH.exists():
        pytest.skip("englishrom.gba not found in input/roms/")
    return EN_ROM_PATH


@pytest.fixture
def es_rom_path():
    if not ES_ROM_PATH.exists():
        pytest.skip("spanishrom.gba not found in input/roms/")
    return ES_ROM_PATH


@pytest.fixture
def fr_rom_path():
    if not FR_ROM_PATH.exists():
        pytest.skip("GenedRom-fr.gba not found in output/roms/")
    return FR_ROM_PATH


@pytest.fixture
def it_rom_path():
    if not IT_ROM_PATH.exists():
        pytest.skip(
            "GenedRom-it.gba not found in output/roms/ — "
            "run: python3 scripts/build_language.py it"
        )
    return IT_ROM_PATH


@pytest.fixture
def translation_ready_path():
    if not TRANSLATION_READY.exists():
        pytest.skip("2026-01-16_translation_ready.json not found")
    return TRANSLATION_READY


@pytest.fixture
def french_texts_path():
    if not FRENCH_TEXTS.exists():
        pytest.skip("french_texts.json not found")
    return FRENCH_TEXTS


@pytest.fixture
def en_rom_data(en_rom_path):
    from src.core.rom_reader import ROMReader
    reader = ROMReader(str(en_rom_path))
    reader.load()
    return reader


@pytest.fixture
def translation_entries(translation_ready_path):
    import json
    with open(translation_ready_path) as f:
        data = json.load(f)
    return data.get("translations", [])


@pytest.fixture(scope="module")
def injected_rom(tmp_path_factory):
    """Inject translations into a copy of the English ROM (module-scoped)."""
    if not EN_ROM_PATH.exists():
        pytest.skip("englishrom.gba not found")
    if not TRANSLATION_READY.exists():
        pytest.skip("translation_ready.json not found")

    import json
    import shutil

    tmp_dir = tmp_path_factory.mktemp("e2e_inject")
    output_path = tmp_dir / "frenchrom_e2e.gba"
    shutil.copy2(EN_ROM_PATH, output_path)

    with open(output_path, "rb") as f:
        rom_data = bytearray(f.read())

    with open(TRANSLATION_READY) as f:
        data = json.load(f)

    from src.core.text_reinserter import SmartReinserter

    reinserter = SmartReinserter(
        rom_data,
        allow_truncate=False,
        allow_relocate=True,
    )

    entries = data.get("translations", [])
    valid = [
        e for e in entries
        if e.get("translation") and not e.get("too_long")
    ]

    for entry in valid[:500]:
        reinserter.reinsert_text({
            "offset": entry["offset"],
            "translation": entry["translation"],
            "encoding": entry.get("encoding", "pokemon"),
            "original_length": entry.get("original_length"),
            "padding_used": entry.get("padding_used"),
        })

    with open(output_path, "wb") as f:
        f.write(rom_data)

    report = reinserter.get_report()
    return output_path, report
