"""Regression guard for the ``make build-fr`` pipeline wiring.

History: ``make build-fr`` once aborted *during inline override processing*
because the EN/ES extraction JSONs were missing — ``apply_inline_overrides_fr.py``
returned a non-zero exit code, which made ``make`` abort the recipe before the
two LZ77 repair steps ever ran. The resulting ROM kept corrupted compressed
graphics blocks and showed a black screen on strict emulators.

The fix has two halves and this test locks in both so the regression cannot
silently come back:

1. ``build-fr`` lists the EN/ES extraction outputs as prerequisites, so they
   are (re)generated automatically and the override step no longer aborts on
   a missing Spanish/English extraction.
2. The recipe still runs *both* LZ77 repair scripts, and runs them **after**
   the inline override step (they are the stages that fix the black-screen
   corruption, so dropping or reordering them re-introduces the bug).

These assertions parse the Makefile only — no ROM required — so they run in the
fast unit tier.

Regression history (short-word translations):
- T-63: short words like "Mom" (3 chars → 4 bytes with 0xFF terminator) were
  silently skipped because the default ``--min-length`` was 12. Lowered to 4.
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"

# Script basenames the recipe must invoke, in pipeline order.
INLINE_OVERRIDE_SCRIPT = "apply_inline_overrides_fr.py"
REPAIR_STABLE_SCRIPT = "repair_stable_lz77_blocks.py"
REPAIR_LOCALIZED_SCRIPT = "repair_localized_lz77_blocks.py"

_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:?=\s*(.*)$")
_VAR_RE = re.compile(r"\$\(([A-Za-z_][A-Za-z0-9_]*)\)")


def _parse_make_vars(text: str) -> dict[str, str]:
    """Collect ``NAME := value`` / ``NAME = value`` assignments."""
    variables: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("\t") or line.lstrip().startswith("#"):
            continue
        match = _ASSIGN_RE.match(line)
        if match:
            variables[match.group(1)] = match.group(2).strip()
    return variables


def _expand(value: str, variables: dict[str, str], _depth: int = 0) -> str:
    """Recursively expand ``$(VAR)`` references (best effort, depth-limited)."""
    if _depth > 25:
        return value

    def repl(match: re.Match) -> str:
        name = match.group(1)
        if name in variables:
            return _expand(variables[name], variables, _depth + 1)
        return match.group(0)

    return _VAR_RE.sub(repl, value)


def _extract_target_block(text: str, target: str) -> tuple[str, str]:
    """Return ``(prerequisites_line, recipe_text)`` for a Makefile target."""
    lines = text.splitlines()
    header_re = re.compile(rf"^{re.escape(target)}\s*:(?!=)\s*(.*)$")
    for i, line in enumerate(lines):
        match = header_re.match(line)
        if not match:
            continue
        prereqs = match.group(1)
        recipe: list[str] = []
        for follow in lines[i + 1:]:
            # Recipe lines are tab-indented; line continuations end with "\".
            if follow.startswith("\t") or (recipe and recipe[-1].rstrip().endswith("\\")):
                recipe.append(follow)
            elif follow.strip() == "":
                continue
            else:
                break
        return prereqs, "\n".join(recipe)
    raise AssertionError(f"Target '{target}' not found in Makefile")


class TestBuildFrPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = MAKEFILE.read_text(encoding="utf-8")
        cls.variables = _parse_make_vars(cls.text)
        cls.prereqs, cls.recipe = _extract_target_block(cls.text, "build-fr")
        cls.prereqs_expanded = _expand(cls.prereqs, cls.variables)
        cls.recipe_expanded = _expand(cls.recipe, cls.variables)

    def test_makefile_exists(self) -> None:
        self.assertTrue(MAKEFILE.exists(), "Makefile is missing")

    def test_build_fr_regenerates_extractions(self) -> None:
        """EN/ES extractions must be prerequisites so they auto-regenerate.

        This is the root-cause fix: when these JSONs were missing the inline
        override step aborted with a non-zero exit code.
        """
        english_extract = _expand("$(ENGLISH_EXTRACT)", self.variables)
        spanish_extract = _expand("$(SPANISH_EXTRACT)", self.variables)
        self.assertIn("englishrom_texts.json", english_extract)
        self.assertIn("spanishrom_texts.json", spanish_extract)
        self.assertIn(
            english_extract,
            self.prereqs_expanded,
            "build-fr must depend on the English extraction so it regenerates",
        )
        self.assertIn(
            spanish_extract,
            self.prereqs_expanded,
            "build-fr must depend on the Spanish extraction so it regenerates",
        )

    def test_build_fr_runs_inline_override(self) -> None:
        self.assertIn(
            INLINE_OVERRIDE_SCRIPT,
            self.recipe_expanded,
            "build-fr must run the inline override step",
        )

    def test_build_fr_runs_both_lz77_repair_steps(self) -> None:
        self.assertIn(
            REPAIR_STABLE_SCRIPT,
            self.recipe_expanded,
            "build-fr must run the stable LZ77 repair step",
        )
        self.assertIn(
            REPAIR_LOCALIZED_SCRIPT,
            self.recipe_expanded,
            "build-fr must run the localized LZ77 repair step",
        )

    def test_lz77_repair_runs_after_inline_override(self) -> None:
        """The repair stages fix the corruption; they must run last."""
        override_at = self.recipe_expanded.find(INLINE_OVERRIDE_SCRIPT)
        stable_at = self.recipe_expanded.find(REPAIR_STABLE_SCRIPT)
        localized_at = self.recipe_expanded.find(REPAIR_LOCALIZED_SCRIPT)
        self.assertNotEqual(override_at, -1)
        self.assertNotEqual(stable_at, -1)
        self.assertNotEqual(localized_at, -1)
        self.assertLess(
            override_at,
            stable_at,
            "stable LZ77 repair must run after the inline override step",
        )
        self.assertLess(
            override_at,
            localized_at,
            "localized LZ77 repair must run after the inline override step",
        )

    def test_repair_scripts_exist(self) -> None:
        for name in (REPAIR_STABLE_SCRIPT, REPAIR_LOCALIZED_SCRIPT, INLINE_OVERRIDE_SCRIPT):
            self.assertTrue(
                (ROOT / "scripts" / name).exists(),
                f"scripts/{name} is missing",
            )


class TestInlineOverrideMinLength(unittest.TestCase):
    """Verify the --min-length default allows 3-char words like 'Mom' (4 bytes with 0xFF)."""

    SCRIPT = ROOT / "scripts" / INLINE_OVERRIDE_SCRIPT

    def _get_min_length_default(self) -> int:
        """Parse the script's argparse definition and return the --min-length default."""
        source = self.SCRIPT.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (func.attr if isinstance(func, ast.Attribute) else
                    func.id if isinstance(func, ast.Name) else None)
            if name != "add_argument":
                continue
            args = [ast.literal_eval(a) for a in node.args if isinstance(a, ast.Constant)]
            if "--min-length" not in args:
                continue
            for kw in node.keywords:
                if kw.arg == "default" and isinstance(kw.value, ast.Constant):
                    return int(kw.value.value)
        raise AssertionError("--min-length argument not found in script")

    def test_min_length_default_allows_short_words(self) -> None:
        """Default must be ≤ 4 so 3-char words (4 bytes incl. 0xFF) are not skipped."""
        default = self._get_min_length_default()
        self.assertLessEqual(
            default,
            4,
            f"--min-length default is {default}; must be ≤ 4 to translate 3-char words like 'Mom'",
        )


if __name__ == "__main__":
    unittest.main()
