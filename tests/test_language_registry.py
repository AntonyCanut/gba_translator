"""Unit tests for the multi-language registry (src/i18n).

These run without any ROM or emulator — they validate the declarative
``languages/<code>/lang.yaml`` descriptors that drive the multi-language build.
"""

from __future__ import annotations

import pytest
import yaml

from src.i18n import LanguageRegistry, RegistryError, load_registry
from src.i18n.registry import REPO_ROOT, _validate
from src.i18n.registry import load_registry as _load

EXPECTED_BUILDABLE = {"fr", "it", "de", "indie"}
EXPECTED_REFERENCES = {"en", "es"}

# Generic (non-dedicated) buildable languages driven by build_language.py.
GENERIC_CODES = ["it", "de", "indie"]


@pytest.fixture(scope="module")
def registry() -> LanguageRegistry:
    return load_registry()


def test_registry_discovers_all_languages(registry):
    assert EXPECTED_BUILDABLE.issubset(set(registry.codes()))
    assert EXPECTED_REFERENCES.issubset(set(registry.codes()))


def test_french_is_complete_and_dedicated(registry):
    fr = registry.get("fr")
    assert fr.is_complete
    assert fr.is_dedicated
    assert fr.build == "dedicated"
    assert fr.combined == "languages/fr/combined_fr.txt"
    assert fr.output_rom == "GenedRom-fr.gba"
    # FR must keep its full proven post-build patch sequence documented.
    assert len(fr.patches) >= 25
    for step in (
        "font",
        "inline",
        "pokedex",
        "status_abbrevs",
        "mission_descriptions",
        "money_amount_order",
    ):
        assert step in fr.patches, f"FR descriptor lost patch step {step!r}"


@pytest.mark.parametrize("code", GENERIC_CODES)
def test_new_languages_are_generic_and_in_progress(registry, code):
    cfg = registry.get(code)
    assert cfg.build == "generic"
    assert cfg.status == "in_progress"
    assert not cfg.is_dedicated


MECHANICAL_PATCHES = {
    "repair_lz77",
    "repair_localized_lz77",
    "repoint_stale",
    "legendary_ritual",
}


@pytest.mark.parametrize("code", GENERIC_CODES)
def test_generic_languages_include_mechanical_patches(registry, code):
    """Generic languages must declare the anti-freeze mechanical patch steps."""
    cfg = registry.get(code)
    missing = MECHANICAL_PATCHES - set(cfg.patches)
    assert not missing, (
        f"{code} descriptor is missing mechanical patch steps: {sorted(missing)}"
    )


@pytest.mark.parametrize("code", GENERIC_CODES)
def test_generic_languages_include_status_abbrevs_patch(registry, code):
    """Generic languages must declare status_abbrevs so abbreviations reach ROM."""
    cfg = registry.get(code)
    assert "status_abbrevs" in cfg.patches, (
        f"{code} descriptor is missing the status_abbrevs patch step"
    )


@pytest.mark.parametrize("code", GENERIC_CODES)
def test_font_patch_runs_after_lz77_repair_steps(registry, code):
    """`font` must be scheduled after repair_lz77/repair_localized_lz77 (B-211).

    Those two steps revert any LZ77 block that is byte-identical between the
    English and Spanish ROMs back to the English reference — and an unpatched
    font block IS byte-identical between EN and ES (neither has the target
    language's extra glyphs). Scheduling `font` before them let every rebuild
    silently wipe the just-drawn glyphs back to blank, even though the charmap
    encoding stayed correct — this is exactly what happened to German ä ö ü.
    The other LZ77 graphic patches (status_badges, type_icons, hp_labels,
    dexnav_headers) already run after the repair steps; `font` must match.
    """
    cfg = registry.get(code)
    if "font" not in cfg.patches:
        pytest.skip(f"{code} has no font step declared")

    font_index = cfg.patches.index("font")
    for repair_step in ("repair_lz77", "repair_localized_lz77"):
        if repair_step not in cfg.patches:
            continue
        repair_index = cfg.patches.index(repair_step)
        assert font_index > repair_index, (
            f"{code} descriptor runs `font` (index {font_index}) before "
            f"`{repair_step}` (index {repair_index}) — the repair step will "
            "revert the font patch's glyph changes on every rebuild"
        )


def test_every_buildable_language_has_required_metadata(registry):
    required_status = {"poison", "burn", "freeze", "paralysis", "sleep", "faint"}
    for cfg in registry.buildable():
        assert cfg.builder_language, f"{cfg.code} missing builder_language"
        assert cfg.output_rom.endswith(".gba"), f"{cfg.code} bad output_rom"
        assert cfg.patch_source.endswith(".gba"), f"{cfg.code} bad patch_source"
        assert cfg.patch_source_path(REPO_ROOT) == (
            REPO_ROOT / cfg.patch_source
        ).resolve(), (
            f"{cfg.code} patch source path is not resolved from the repository"
        )
        assert cfg.version_label, f"{cfg.code} missing version_label"
        assert required_status.issubset(set(cfg.status_abbrev)), (
            f"{cfg.code} status_abbrev missing keys"
        )


def test_reference_languages_have_no_output_rom(registry):
    for cfg in registry.references():
        assert cfg.is_reference
        assert not cfg.output_rom, f"{cfg.code} should have no output_rom"
        assert cfg.output_rom_path(REPO_ROOT) is None


def test_spanish_is_reference_with_font_glyphs(registry):
    """ES has no build of its own (see tests/e2e/es/) — it is the community
    translation ROM used as a reference by the pointer-based pipeline."""
    es = registry.get("es")
    assert es.is_reference
    assert es.status == "reference"
    assert es.build == "none"
    assert es.combined == "languages/es/combined_es.txt"
    assert set("áéíóúñ¡¿").issubset(set(es.font_glyphs))


def test_combined_files_exist(registry):
    for cfg in registry:
        assert cfg.combined_path(REPO_ROOT).exists(), (
            f"combined file missing for {cfg.code}: {cfg.combined}"
        )


def test_output_rom_names_are_unique(registry):
    roms = [cfg.output_rom for cfg in registry.buildable()]
    assert len(roms) == len(set(roms)), "duplicate output ROM names in registry"


def test_patch_sources_match_the_real_build_lineages(registry):
    """Toutes les releases doivent s'appliquer à la même ROM anglaise propre."""
    for code in ["fr", *GENERIC_CODES]:
        assert registry.get(code).patch_source == "input/roms/englishrom.gba"


def test_buildable_orders_french_first(registry):
    order = [cfg.code for cfg in registry.buildable()]
    assert order[0] == "fr"
    # Reference languages must NOT appear in the buildable list
    ref_codes = {cfg.code for cfg in registry.references()}
    assert not ref_codes.intersection(set(order))


def test_translation_json_paths_are_distinct(registry):
    paths = {cfg.translation_json_path(REPO_ROOT) for cfg in registry.buildable()}
    assert len(paths) == len(registry.buildable())


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
        "build: generic\ncombined: c.txt\noutput_rom: GenedRom-yy.gba\n"
        "patch_source: input/roms/englishrom.gba\n",
        encoding="utf-8",
    )
    with pytest.raises(RegistryError):
        _validate(yaml.safe_load(bad.read_text()), bad)


def test_load_registry_empty_dir_raises(tmp_path):
    with pytest.raises(RegistryError):
        _load(tmp_path)


def test_validate_rejects_buildable_language_without_patch_source(tmp_path):
    """Une release ne doit pas deviner la ROM de base d'une langue."""
    bad = tmp_path / "xx" / "lang.yaml"
    bad.parent.mkdir(parents=True)
    bad.write_text(
        "code: xx\nname: X\nbuilder_language: x\nstatus: in_progress\n"
        "build: generic\ncombined: c.txt\noutput_rom: GenedRom-xx.gba\n",
        encoding="utf-8",
    )

    with pytest.raises(RegistryError, match="patch_source"):
        _validate(yaml.safe_load(bad.read_text()), bad)
