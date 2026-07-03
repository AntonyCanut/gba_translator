"""Tests for the generic build driver's patch dispatch (build_language.apply_patches).

These tests verify that each new patch step declared in a lang.yaml descriptor
is correctly forwarded to the right subprocess call, without touching any real
ROM (the ``run()`` helper is mocked out).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List
from unittest.mock import call, patch as mock_patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_language import (
    AUDIT_COLLISIONS_SCRIPT,
    ENGLISH_ROM,
    PATCH_RITUAL_SCRIPT,
    PATCH_STATUS_ABBREVS_SCRIPT,
    PATCH_TM_ITEM_DESC_SCRIPT,
    PATCH_VERSION_SCRIPT,
    PYTHON,
    REPAIR_LOCALIZED_LZ77_SCRIPT,
    REPAIR_LZ77_SCRIPT,
    REPOINT_STALE_SCRIPT,
    SPANISH_ROM,
    apply_patches,
)
from src.i18n import load_registry

REGISTRY = load_registry()


def _collected_calls(config, steps: List[str], translation_json=None,
                     build_number=0) -> list:
    """Run apply_patches with a patched ``run()`` and collect calls."""

    class _FakeConfig:
        code = config.code
        patches = steps

        def combined_path(self, root):
            return config.combined_path(root)

    fake_rom = Path("/tmp/fake_rom.gba")
    calls_made = []

    def fake_run(cmd, *, cwd=None):
        calls_made.append([str(p) for p in cmd])

    with mock_patch("scripts.build_language.run", side_effect=fake_run):
        apply_patches(_FakeConfig(), fake_rom, translation_json, build_number)

    return calls_made


# ─── repair_lz77 ────────────────────────────────────────────────────────────

def test_repair_lz77_dispatches_stable_script():
    config = REGISTRY.get("it")
    calls = _collected_calls(config, ["repair_lz77"])
    assert len(calls) == 1
    cmd = calls[0]
    assert str(REPAIR_LZ77_SCRIPT) in cmd
    assert "--target" in cmd
    assert str(ENGLISH_ROM) in cmd
    assert str(SPANISH_ROM) in cmd


# ─── repair_localized_lz77 ──────────────────────────────────────────────────

def test_repair_localized_lz77_passes_require_pointer():
    config = REGISTRY.get("it")
    calls = _collected_calls(config, ["repair_localized_lz77"])
    assert len(calls) == 1
    cmd = calls[0]
    assert str(REPAIR_LOCALIZED_LZ77_SCRIPT) in cmd
    assert "--require-pointer" in cmd


# ─── repoint_stale ──────────────────────────────────────────────────────────

def test_repoint_stale_skipped_without_json(capsys):
    config = REGISTRY.get("it")
    calls = _collected_calls(config, ["repoint_stale"], translation_json=None)
    assert calls == []
    captured = capsys.readouterr()
    assert "skipping repoint_stale" in captured.out


def test_repoint_stale_dispatches_with_json():
    config = REGISTRY.get("it")
    fake_json = Path("/tmp/it_translation_ready.json")
    calls = _collected_calls(config, ["repoint_stale"], translation_json=fake_json)
    assert len(calls) == 1
    cmd = calls[0]
    assert str(REPOINT_STALE_SCRIPT) in cmd
    assert "--translations" in cmd
    assert str(fake_json) in cmd
    assert str(ENGLISH_ROM) in cmd


# ─── legendary_ritual ───────────────────────────────────────────────────────

def test_legendary_ritual_dispatches_with_english_source():
    config = REGISTRY.get("de")
    calls = _collected_calls(config, ["legendary_ritual"])
    assert len(calls) == 1
    cmd = calls[0]
    assert str(PATCH_RITUAL_SCRIPT) in cmd
    assert "--source" in cmd
    assert str(ENGLISH_ROM) in cmd


# ─── status_abbrevs ─────────────────────────────────────────────────────────

def test_status_abbrevs_passes_lang_code_it():
    config = REGISTRY.get("it")
    calls = _collected_calls(config, ["status_abbrevs"])
    assert len(calls) == 1
    cmd = calls[0]
    assert str(PATCH_STATUS_ABBREVS_SCRIPT) in cmd
    assert "--lang-code" in cmd
    lang_idx = cmd.index("--lang-code")
    assert cmd[lang_idx + 1] == "it"


def test_status_abbrevs_passes_lang_code_de():
    config = REGISTRY.get("de")
    calls = _collected_calls(config, ["status_abbrevs"])
    assert len(calls) == 1
    cmd = calls[0]
    lang_idx = cmd.index("--lang-code")
    assert cmd[lang_idx + 1] == "de"


# ─── status_badges ──────────────────────────────────────────────────────────

def test_status_badges_dispatches_de_script():
    # The graphical badge step must resolve to the DE-specific tile patch.
    config = REGISTRY.get("de")
    calls = _collected_calls(config, ["status_badges"])
    assert len(calls) == 1
    cmd = calls[0]
    assert any(c.endswith("patch_status_badges_de.py") for c in cmd)
    assert "--rom" in cmd


def test_status_badges_in_de_descriptor():
    # The DE descriptor must request the graphical status badge patch.
    assert "status_badges" in REGISTRY.get("de").patches


# ─── dexnav_headers ──────────────────────────────────────────────────────────

def test_dexnav_headers_dispatches_de_script():
    # The DexNav header graphics step must resolve to the DE-specific tile patch.
    config = REGISTRY.get("de")
    calls = _collected_calls(config, ["dexnav_headers"])
    assert len(calls) == 1
    cmd = calls[0]
    assert any(c.endswith("patch_dexnav_headers_de.py") for c in cmd)
    assert "--rom" in cmd


def test_dexnav_headers_in_de_descriptor():
    # The DE descriptor must request the graphical DexNav header patch.
    assert "dexnav_headers" in REGISTRY.get("de").patches


# ─── version ─────────────────────────────────────────────────────────────────

def test_version_step_passes_lang_code_and_build_number():
    config = REGISTRY.get("it")
    calls = _collected_calls(config, ["version"], build_number=42)
    assert len(calls) == 1
    cmd = calls[0]
    assert str(PATCH_VERSION_SCRIPT) in cmd
    assert "--lang-code" in cmd
    assert cmd[cmd.index("--lang-code") + 1] == "it"
    assert "--build-number" in cmd
    assert cmd[cmd.index("--build-number") + 1] == "42"


def test_version_step_in_it_descriptor():
    # The IT descriptor must request the in-game version tag so the build
    # advertises itself as Italian.
    config = REGISTRY.get("it")
    assert "version" in config.patches


# ─── collision_check ─────────────────────────────────────────────────────────

def test_collision_check_dispatches_audit_report_only():
    config = REGISTRY.get("de")
    calls = _collected_calls(config, ["collision_check"])
    assert len(calls) == 1
    cmd = calls[0]
    assert str(AUDIT_COLLISIONS_SCRIPT) in cmd
    assert "--combined" in cmd
    assert "--rom" in cmd
    assert "--english" in cmd and str(ENGLISH_ROM) in cmd
    # Report-only: the build step must never abort on a pre-existing collision.
    assert "--fail-on-collision" not in cmd


def test_collision_check_in_de_and_it_descriptors():
    assert "collision_check" in REGISTRY.get("de").patches
    assert "collision_check" in REGISTRY.get("it").patches


# ─── unknown step warning ────────────────────────────────────────────────────

def test_unknown_step_prints_warning(capsys):
    config = REGISTRY.get("it")
    calls = _collected_calls(config, ["nonexistent_step"])
    assert calls == []
    out = capsys.readouterr().out
    assert "skipping" in out
    assert "nonexistent_step" in out


# ─── full IT descriptor patch sequence ──────────────────────────────────────

def test_it_descriptor_patches_all_dispatch():
    """Every step currently in the IT descriptor must dispatch at least one call."""
    config = REGISTRY.get("it")
    fake_json = Path("/tmp/it_translation_ready.json")
    calls = _collected_calls(config, config.patches, translation_json=fake_json)
    # font + inline + repair_lz77 + repair_localized_lz77 + repoint_stale
    # + legendary_ritual + status_abbrevs = 7 calls
    assert len(calls) == len(config.patches), (
        f"Expected {len(config.patches)} subprocess calls for IT patches, "
        f"got {len(calls)}: {calls}"
    )


def test_de_descriptor_patches_all_dispatch():
    config = REGISTRY.get("de")
    fake_json = Path("/tmp/de_translation_ready.json")
    calls = _collected_calls(config, config.patches, translation_json=fake_json)
    assert len(calls) == len(config.patches)
