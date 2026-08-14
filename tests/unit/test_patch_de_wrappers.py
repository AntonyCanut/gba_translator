"""Tests for the German pointer-relocation post-build wrappers.

``languages/de/patches/mission_descriptions.py`` and
``worldmap_junction_panels.py`` are thin wrappers that delegate to the
language-agnostic ``languages/fr/patches/<name>.py`` implementation via
``src.i18n.fr_patch_delegate``, re-pointed at ``languages/de/combined_de.txt``.

These assert, without touching a 32 MB ROM, that each wrapper:
* targets the correct FR script + ``--rom`` and passes ``--source`` + the German
  combined file (never French data);
* is dispatched WITHOUT ``--reference-rom`` — the crux of the F-83 free-space
  fix. The packed DE build leaves ~0 bytes free in *both* EN and ES, so
  excluding Spanish-populated bytes (``--reference-rom``) aborts the relocation
  with ``0/47 FAILED (free space)``. Omitting it lets the patch harvest the
  EN-free/ES-populated pool the main-text pass avoids, which relocates all
  47 missions + 9 junction panels;
* passes only flags the FR delegate actually accepts (``--help``).
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

# wrapper/step name → flags it must pass to the FR implementation.
WRAPPERS = {
    "mission_descriptions": ["--source", "--combined"],
    "worldmap_junction_panels": ["--source", "--combined"],
    "zone_names": ["--source", "--combined"],
}

DUMMY_ROM = Path("/tmp/dummy-de-rom.gba")


def _de_wrapper(name: str):
    return importlib.import_module(f"languages.de.patches.{name}")


@pytest.mark.parametrize("name,flags", list(WRAPPERS.items()))
def test_wrapper_targets_correct_fr_script(name, flags):
    mod = _de_wrapper(name)
    cmd = [str(part) for part in mod.make_command(DUMMY_ROM)]

    assert cmd[0] == sys.executable or cmd[0] == "python3"
    assert any(arg.endswith(f"languages/fr/patches/{name}.py") for arg in cmd), cmd
    assert "--rom" in cmd and str(DUMMY_ROM) in cmd
    for flag in flags:
        assert flag in cmd, f"{name} must pass {flag}: {cmd}"


@pytest.mark.parametrize("name", list(WRAPPERS))
def test_wrapper_points_at_german_combined_not_french(name):
    mod = _de_wrapper(name)
    cmd = " ".join(str(part) for part in mod.make_command(DUMMY_ROM))

    assert "languages/de/combined_de.txt" in cmd, cmd
    assert "combined_fr.txt" not in cmd, cmd
    assert "combined_it.txt" not in cmd, cmd


@pytest.mark.parametrize("name", ["mission_descriptions", "worldmap_junction_panels", "zone_names"])
def test_wrapper_omits_reference_rom(name):
    """The F-83 fix: NO --reference-rom, so reserved=None harvests the
    EN-free/ES-populated pool instead of aborting on 0 EN∩ES-free space."""
    mod = _de_wrapper(name)
    cmd = [str(part) for part in mod.make_command(DUMMY_ROM)]

    assert "--reference-rom" not in cmd, (
        f"{name} must NOT pass --reference-rom in the packed DE build: {cmd}"
    )
    assert not any("spanishrom" in arg for arg in cmd), cmd


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


@pytest.mark.parametrize("name", list(WRAPPERS))
def test_de_descriptor_wires_wrapper_at_end(name):
    """Both steps must be declared in the DE descriptor and run at the very end
    (after `inline` and every other relocation) so nothing overwrites the bytes
    they harvest from the ES-populated free-space pool."""
    from scripts import build_language  # noqa: F401 — ensures import path is set
    import yaml

    descriptor = yaml.safe_load(
        (ROOT / "languages" / "de" / "lang.yaml").read_text(encoding="utf-8")
    )
    patches = descriptor["patches"]
    assert name in patches, f"{name} not wired into languages/de/lang.yaml"
    # Must come after the inline mirror pass.
    assert patches.index("inline") < patches.index(name), (
        f"{name} must run after `inline` so reserved=None stays safe"
    )
    # Only non-relocating finalizers may follow: the species-table restore is
    # deliberately last among writers so no earlier pass can relocalise names.
    assert set(patches[patches.index(name) + 1:]) <= {
        "mission_descriptions",
        "worldmap_junction_panels",
        "zone_names",
        "species_names",
        "collision_check",
    }, f"{name} must be among the last relocation steps: {patches}"
