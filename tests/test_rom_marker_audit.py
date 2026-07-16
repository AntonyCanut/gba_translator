"""Audit that built-ROM tests stay out of the fast pytest target."""

from __future__ import annotations

import ast
from pathlib import Path


TESTS_ROOT = Path(__file__).resolve().parent


def _string_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def _mentions_built_rom(path: Path) -> bool:
    literals = _string_literals(path)
    joined = "\n".join(literals)
    if "GenedRom-" not in joined or ".gba" not in joined:
        return False
    if "output/roms" in joined or "output\\roms" in joined:
        return True
    return "output" in literals and "roms" in literals


def _has_rom_marker(path: Path) -> bool:
    source = path.read_text(encoding="utf-8")
    return "pytestmark = pytest.mark.rom" in source or "@pytest.mark.rom" in source


def test_built_rom_tests_are_marked_rom() -> None:
    offenders = []
    for path in sorted(TESTS_ROOT.rglob("test_*.py")):
        if path == Path(__file__).resolve():
            continue
        if _mentions_built_rom(path) and not _has_rom_marker(path):
            offenders.append(str(path.relative_to(TESTS_ROOT.parent)))

    assert offenders == []
