"""Packaging guard: the runtime dependencies CI installs must cover everything
the build actually imports.

Why this exists
---------------
``make build-it`` / ``make build-de`` import ``src.i18n.registry`` which does
``import yaml``.  CI installs the project with ``pip install -e ".[dev]"``, so a
dependency that is *used at build time* but *not declared* in
``[project].dependencies`` works on a dev machine (PyYAML already present) yet
crashes in CI with ``ModuleNotFoundError: No module named 'yaml'`` — exactly the
B-84 Italian-build failure.

This test asserts the declaration exists so a future edit can't silently drop it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = REPO_ROOT / "pyproject.toml"


def _runtime_dependencies() -> list[str]:
    """Return ``[project].dependencies`` from pyproject.toml.

    Uses tomllib when available (Python >=3.11, as CI runs), and falls back to a
    minimal regex parse so the guard also runs under the local 3.9 interpreter
    used by the pre-commit hook.
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    try:
        import tomllib  # Python >=3.11

        return tomllib.loads(text).get("project", {}).get("dependencies", [])
    except ModuleNotFoundError:
        # Fallback: extract the dependencies = [ ... ] array literal.
        match = re.search(r"^dependencies\s*=\s*(\[.*?\])", text, re.MULTILINE | re.DOTALL)
        if not match:
            return []
        return list(ast.literal_eval(match.group(1)))


def test_pyyaml_is_a_declared_runtime_dependency():
    """src/i18n/registry.py imports yaml — it must be a declared runtime dep."""
    deps = _runtime_dependencies()
    assert any(
        dep.lower().replace("-", "").startswith("pyyaml") for dep in deps
    ), (
        "pyyaml must be in [project].dependencies of pyproject.toml so CI's "
        f"`pip install -e .` installs it for the IT/DE builds. Got: {deps}"
    )
