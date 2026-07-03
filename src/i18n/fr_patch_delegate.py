#!/usr/bin/env python3
"""Delegate a language-agnostic ``patch_*_fr.py`` post-build patch to another
language.

Many of the French post-build patches are *not* French-specific: they either
read the text they inject straight from a ``--combined`` / ``--translations``
file (so pointing them at ``languages/it/combined_it.txt`` produces genuine
Italian), or they restore language-independent bytes from the English/Spanish
source ROMs (control-code clusters, tilemaps, item structs, …).

Rather than fork ~200 lines of proven French code per language, the Italian
``scripts/patch_<name>_it.py`` wrappers are thin: they resolve the Italian data
sources and re-invoke the shared ``patch_<name>_fr.py`` implementation through
this helper. ``build_command`` is a pure function so tests can assert the exact
argument list without touching a 32 MB ROM.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

ENGLISH_ROM = REPO_ROOT / "input/roms/englishrom.gba"
SPANISH_ROM = REPO_ROOT / "input/roms/spanishrom.gba"

PYTHON = sys.executable or "python3"


def build_command(
    fr_script: str,
    rom: Path,
    *,
    combined: Path | None = None,
    combined_en: Path | None = None,
    source: bool = False,
    reference_rom: bool = False,
    translations: Path | None = None,
    overrides: Path | None = None,
    extra: list[str] | None = None,
    python: str | None = None,
) -> list[str]:
    """Return the argv that runs ``fr_script`` against ``rom`` with the given
    language data sources.

    * ``combined`` / ``combined_en`` → ``--combined`` / ``--combined-en``
    * ``source`` → ``--source <englishrom.gba>``
    * ``reference_rom`` → ``--reference-rom <spanishrom.gba>`` (only if present)
    * ``translations`` → ``--translations <json>``
    * ``overrides`` → ``--overrides <json>`` (pass an empty file to suppress the
      French curated overrides that would otherwise leak into another language)
    """
    py = python or PYTHON
    cmd: list[str] = [py, str(SCRIPTS_DIR / fr_script), "--rom", str(rom)]
    if combined is not None:
        cmd += ["--combined", str(combined)]
    if combined_en is not None:
        cmd += ["--combined-en", str(combined_en)]
    if source:
        cmd += ["--source", str(ENGLISH_ROM)]
    if reference_rom and SPANISH_ROM.exists():
        cmd += ["--reference-rom", str(SPANISH_ROM)]
    if translations is not None:
        cmd += ["--translations", str(translations)]
    if overrides is not None:
        cmd += ["--overrides", str(overrides)]
    if extra:
        cmd += list(extra)
    return cmd


def run(cmd: list[str]) -> int:
    """Execute a command built by :func:`build_command` from the repo root."""
    printable = " ".join(str(part) for part in cmd)
    print(f"\n$ {printable}")
    return subprocess.run([str(part) for part in cmd], cwd=str(REPO_ROOT)).returncode
