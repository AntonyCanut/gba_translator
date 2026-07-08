"""Tests for the German move-name and species-name fixed-table wrappers
(issue #81: "Pokemon Namen und Attacken Namen sind alle auf Englisch").

``languages/de/patches/move_names.py`` and ``species_names.py`` are thin
wrappers that delegate to the language-agnostic ``languages/fr/patches/
<name>.py`` implementation via ``src.i18n.fr_patch_delegate``, re-pointed at
``languages/de/combined_de.txt``. These assert, without touching a 32 MB ROM,
that each wrapper targets the correct FR script and German data, and that
both steps are wired into the German build descriptor.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from languages.de.patches import move_names as de_move_names  # noqa: E402
from languages.de.patches import species_names as de_species_names  # noqa: E402

DUMMY_ROM = Path("/tmp/dummy-de-rom.gba")


def test_move_names_wrapper_targets_fr_script_and_german_data():
    cmd = [str(part) for part in de_move_names.make_command(DUMMY_ROM)]

    assert any(arg.endswith("languages/fr/patches/move_names.py") for arg in cmd), cmd
    assert "--rom" in cmd and str(DUMMY_ROM) in cmd
    joined = " ".join(cmd)
    assert "languages/de/combined_de.txt" in joined
    assert "combined_fr.txt" not in joined
    assert "combined_it.txt" not in joined


def test_species_names_wrapper_targets_fr_script_and_german_data():
    cmd = [str(part) for part in de_species_names.make_command(DUMMY_ROM)]

    assert any(arg.endswith("languages/fr/patches/species_names.py") for arg in cmd), cmd
    assert "--rom" in cmd and str(DUMMY_ROM) in cmd
    joined = " ".join(cmd)
    assert "languages/de/combined_de.txt" in joined
    assert "combined_fr.txt" not in joined
    assert "combined_it.txt" not in joined


def test_de_descriptor_wires_both_steps():
    descriptor = yaml.safe_load(
        (ROOT / "languages" / "de" / "lang.yaml").read_text(encoding="utf-8")
    )
    patches = descriptor["patches"]
    assert "move_names" in patches, "move_names not wired into languages/de/lang.yaml"
    assert "species_names" in patches, "species_names not wired into languages/de/lang.yaml"
