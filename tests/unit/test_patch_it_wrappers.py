"""Tests for the Italian post-build patch wrappers ported from the French pipeline.

Each ``languages/it/patches/<name>.py`` is a thin wrapper that delegates to the
language-agnostic ``languages/fr/patches/<name>.py`` via
``src.i18n.fr_patch_delegate``, re-pointed at the Italian data sources
(``languages/it/combined_it.txt`` or the Italian translation-ready JSON).

These tests assert, without touching a 32 MB ROM, that:
* every wrapper builds a command targeting the correct FR script + ``--rom``;
* the wrapper points at Italian data and NEVER at a French source/override
  (no ``combined_fr.txt``, no ``languages/fr`` data path, no ``*_fr_overrides.json``);
* the FR delegate actually accepts every flag the wrapper passes (``--help``);
* ``build_language`` dispatches each declared IT ``lang.yaml`` step, and every
  step resolves to either a wrapper or a built-in handler branch;
* the Italian description-override files exist and are empty JSON objects.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))  # build_language is imported by bare name

# wrapper/step name → flags it must pass. The IT wrapper
# ``languages/it/patches/<name>.py`` delegates to the FR implementation
# ``languages/fr/patches/<name>.py`` (same basename).
WRAPPERS = {
    "ability_names": ["--combined", "--combined-en"],
    "tm_item_descriptions": ["--combined"],
    "dup_move_descriptions": ["--combined"],
    "meteorite_dialogue": ["--source", "--combined"],
    "mission_descriptions": ["--source", "--combined"],
    "battle_string_templates": ["--source"],
    "givecs_gift_item": ["--source"],
    "summary_labels": ["--source"],
    "move_descriptions": ["--source", "--translations", "--overrides"],
    # NOTE: pokedex is NOT a thin FR-delegating wrapper for Italian — the base
    # ships a full languages/it/patches/pokedex.py rewrap port (dispatched by
    # pokedex_rewrap, not the generic --rom path), so it is intentionally absent.
}

DUMMY_ROM = Path("/tmp/dummy-it-rom.gba")


def _it_wrapper(name: str):
    return importlib.import_module(f"languages.it.patches.{name}")


@pytest.mark.parametrize("name,flags", list(WRAPPERS.items()))
def test_wrapper_targets_correct_fr_script(name, flags):
    mod = _it_wrapper(name)
    cmd = [str(part) for part in mod.make_command(DUMMY_ROM)]

    assert cmd[0] == sys.executable or cmd[0] == "python3"
    assert any(arg.endswith(f"languages/fr/patches/{name}.py") for arg in cmd), cmd
    assert "--rom" in cmd and str(DUMMY_ROM) in cmd
    for flag in flags:
        assert flag in cmd, f"{name} must pass {flag}: {cmd}"


@pytest.mark.parametrize("name", list(WRAPPERS))
def test_wrapper_never_references_french_data(name):
    mod = _it_wrapper(name)
    cmd = " ".join(str(part) for part in mod.make_command(DUMMY_ROM))

    assert "combined_fr.txt" not in cmd, cmd
    assert "languages/fr/data" not in cmd, cmd
    assert "languages/fr/combined" not in cmd, cmd
    assert "_fr_overrides.json" not in cmd, cmd
    assert "translation_ready_fr" not in cmd, cmd


def test_combined_wrappers_point_at_italian_combined():
    for name in ("ability_names", "tm_item_descriptions",
                 "meteorite_dialogue", "mission_descriptions"):
        mod = _it_wrapper(name)
        cmd = " ".join(str(p) for p in mod.make_command(DUMMY_ROM))
        assert "languages/it/combined_it.txt" in cmd, name


def test_json_wrappers_point_at_italian_json_and_empty_overrides():
    for name in ("move_descriptions",):
        mod = _it_wrapper(name)
        cmd = " ".join(str(p) for p in mod.make_command(DUMMY_ROM))
        assert "it_translation_ready.json" in cmd, name
        assert "_it_overrides.json" in cmd, name


@pytest.mark.parametrize("name,flags", list(WRAPPERS.items()))
def test_fr_delegate_accepts_every_flag(name, flags):
    """The FR target must actually accept the flags the wrapper passes."""
    fr_script = ROOT / "languages" / "fr" / "patches" / f"{name}.py"
    help_out = subprocess.run(
        [sys.executable, str(fr_script), "--help"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=60,
    )
    assert help_out.returncode == 0, help_out.stderr
    text = help_out.stdout + help_out.stderr
    for flag in flags + ["--rom"]:
        assert flag in text, f"{fr_script.name} help is missing {flag}"


def test_overrides_files_are_empty_json():
    for name in ("move_descriptions_it_overrides.json", "pokedex_it_overrides.json"):
        data = json.loads((ROOT / "languages" / "it" / "data" / name).read_text(encoding="utf-8"))
        assert data == {}, name


# ── build_language dispatch integration ─────────────────────────────────────────

def _load_build_language():
    return importlib.import_module("build_language")


def test_lang_patch_script_resolves_ported_wrappers():
    bl = _load_build_language()
    for step in ("ability_names", "meteorite_dialogue", "summary_labels", "tm_item_descriptions"):
        script = bl._lang_patch_script(step, "it")
        assert script is not None and script.name == f"{step}.py", step
        assert script.parent == ROOT / "languages" / "it" / "patches", step
    # A suffixed step (intro_questions_it) resolves to its own script.
    intro = bl._lang_patch_script("intro_questions_it", "it")
    assert intro is not None and intro.name == "intro_questions.py"
    # An un-ported step returns None (falls back to the shared FR branches).
    assert bl._lang_patch_script("repair_lz77", "it") is None


# Steps handled directly by the apply_patches() if/elif chain (no _it wrapper).
# pokedex_rewrap resolves its script as languages/it/patches/pokedex.py (a name
# that does not match a "pokedex_rewrap" wrapper), so it is dispatched by the
# elif branch with --source/--translations, not the generic --rom wrapper path.
_BUILTIN_STEPS = {
    "font", "inline", "repair_lz77", "repair_localized_lz77", "repoint_stale",
    "legendary_ritual", "intro_questions_it", "version", "status_abbrevs",
    "tm_item_descriptions", "move_descriptions", "pokedex_rewrap", "collision_check",
}


def test_every_italian_step_is_dispatchable():
    """No declared IT patch step is silently dropped by apply_patches()."""
    from src.i18n import load_registry

    bl = _load_build_language()
    config = load_registry().get("it")
    for step in config.patches:
        resolved = bl._lang_patch_script(step, "it") is not None or step in _BUILTIN_STEPS
        assert resolved, f"IT step {step!r} has neither a wrapper nor a builtin handler"


def test_ported_wrapper_scripts_exist_on_disk():
    for name in WRAPPERS:
        assert (ROOT / "languages" / "it" / "patches" / f"{name}.py").exists(), name
