"""Guard: every patch script reachable by the generic ``--rom``-only dispatch
must be self-contained.

``build_language.apply_patches`` resolves ``scripts/patch_<step>_<code>.py``
ahead of the shared French branches (see ``_lang_patch_script``) and invokes it
with a single ``--rom`` argument. Any such script that declares another
``required=True`` argument (e.g. ``--source``) would abort the whole build with
an argparse "the following arguments are required" error.

This regression test — which would have caught the German ``givecs_gift_item`` /
``battle_string_templates`` scripts shipping ``--source required=True`` — checks
that for every declared patch step of every generic-build language, whatever
``_lang_patch_script`` resolves accepts ``--rom`` on its own.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.i18n import load_registry  # noqa: E402

bl = importlib.import_module("build_language")


def _required_non_rom_args(script: Path) -> list[str]:
    """Return the non-``--rom`` option strings the script marks required=True."""
    tree = ast.parse(script.read_text(encoding="utf-8"))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            continue
        required = any(
            kw.arg == "required"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is True
            for kw in node.keywords
        )
        if not required:
            continue
        opts = [a.value for a in node.args
                if isinstance(a, ast.Constant) and isinstance(a.value, str)
                and a.value.startswith("--")]
        for opt in opts:
            if opt != "--rom":
                offenders.append(opt)
    return offenders


def _generic_languages():
    registry = load_registry()
    for code in registry.codes():
        config = registry.get(code)
        if getattr(config, "is_dedicated", False):
            continue  # French: dedicated recipe, never uses the generic dispatch
        yield config


# (lang_code, step, resolved_script_path) for every generically-dispatched step.
_CASES = [
    (config.code, step, bl._lang_patch_script(step, config.code))
    for config in _generic_languages()
    for step in config.patches
]
_DISPATCHED = [(code, step, path) for code, step, path in _CASES if path is not None]


def test_some_steps_are_generically_dispatched():
    # Sanity: the resolver actually finds wrappers, else the guard below is vacuous.
    assert _DISPATCHED, "no generic --rom dispatch resolved any patch script"


@pytest.mark.parametrize(
    "code,step,path",
    _DISPATCHED,
    ids=[f"{code}:{step}" for code, step, _ in _DISPATCHED],
)
def test_generically_dispatched_script_is_rom_only(code, step, path):
    offenders = _required_non_rom_args(path)
    assert not offenders, (
        f"{path.name} is dispatched with only --rom by build_language for "
        f"language {code!r} step {step!r}, but declares required arg(s) "
        f"{offenders} — give them a default so the generic build does not abort."
    )
