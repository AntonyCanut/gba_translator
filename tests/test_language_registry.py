"""Unit tests for the multi-language registry (src/i18n).

These run without any ROM or emulator — they validate the declarative
``languages/<code>/lang.yaml`` descriptors that drive the multi-language build.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.i18n import LanguageRegistry, RegistryError, load_registry
from src.i18n.registry import REPO_ROOT, _validate, load_registry as _load

EXPECTED_LANGUAGES = {"fr", "it", "de"}


@pytest.fixture(scope="module")
def registry() -> LanguageRegistry:
    return load_registry()


def test_registry_discovers_all_languages(registry):
    assert EXPECTED_LANGUAGES.issubset(set(registry.codes()))


def test_french_is_complete_and_dedicated(registry):
    fr = registry.get("fr")
    assert fr.is_complete
    assert fr.is_dedicated
    assert fr.build == "dedicated"
    assert fr.combined == "languages/fr/combined_fr.txt"
    assert fr.output_rom == "GenedRom-fr.gba"
    # FR must keep its full proven post-build patch sequence documented.
    assert len(fr.patches) >= 25
    for step in ("font", "inline", "pokedex", "status_abbrevs", "mission_descriptions"):
        assert step in fr.patches, f"FR descriptor lost patch step {step!r}"


@pytest.mark.parametrize("code", ["it", "de"])
def test_new_languages_are_generic_and_in_progress(registry, code):
    cfg = registry.get(code)
    assert cfg.build == "generic"
    assert cfg.status == "in_progress"
    assert not cfg.is_dedicated


def test_every_language_has_required_metadata(registry):
    required_status = {"poison", "burn", "freeze", "paralysis", "sleep", "faint"}
    for cfg in registry:
        assert cfg.builder_language
        assert cfg.output_rom.endswith(".gba")
        assert cfg.version_label, f"{cfg.code} missing version_label"
        assert required_status.issubset(set(cfg.status_abbrev)), (
            f"{cfg.code} status_abbrev missing keys"
        )


def test_combined_files_exist(registry):
    for cfg in registry:
        assert cfg.combined_path(REPO_ROOT).exists(), (
            f"combined file missing for {cfg.code}: {cfg.combined}"
        )


def test_output_rom_names_are_unique(registry):
    roms = [cfg.output_rom for cfg in registry]
    assert len(roms) == len(set(roms)), "duplicate output ROM names in registry"


def test_buildable_orders_french_first(registry):
    order = [cfg.code for cfg in registry.buildable()]
    assert order[0] == "fr"


def test_translation_json_paths_are_distinct(registry):
    paths = {cfg.translation_json_path(REPO_ROOT) for cfg in registry}
    assert len(paths) == len(registry)


def test_get_unknown_language_raises(registry):
    with pytest.raises(RegistryError):
        registry.get("xx")


def test_validate_rejects_missing_key(tmp_path):
    bad = tmp_path / "xx" / "lang.yaml"
    bad.parent.mkdir(parents=True)
    bad.write_text("code: xx\nname: X\n", encoding="utf-8")
    with pytest.raises(RegistryError):
        _validate(yaml.safe_load(bad.read_text()), bad)


def test_validate_rejects_code_folder_mismatch(tmp_path):
    bad = tmp_path / "zz" / "lang.yaml"
    bad.parent.mkdir(parents=True)
    bad.write_text(
        "code: yy\nname: Y\nbuilder_language: y\nstatus: in_progress\n"
        "build: generic\ncombined: c.txt\noutput_rom: GenedRom-yy.gba\n",
        encoding="utf-8",
    )
    with pytest.raises(RegistryError):
        _validate(yaml.safe_load(bad.read_text()), bad)


def test_load_registry_empty_dir_raises(tmp_path):
    with pytest.raises(RegistryError):
        _load(tmp_path)
