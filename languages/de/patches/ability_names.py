#!/usr/bin/env python3
"""German port of ``patch_ability_names_fr`` — patches the fixed-width 17-byte
ability-name table, sourcing the German names from
``languages/de/combined_de.txt`` and validating each cell against
``languages/en/combined_en.txt``.

The French implementation is fully data-driven (``--combined`` / ``--combined-en``),
so this wrapper only re-points it at the German data. See
``src.i18n.fr_patch_delegate`` for the delegation mechanism.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from languages.de.terminology import section as terminology_section  # noqa: E402
from languages.fr.patches import ability_names as ability_table  # noqa: E402
from src.i18n.fr_patch_delegate import build_command, run  # noqa: E402

DE_COMBINED = REPO_ROOT / "languages/de/combined_de.txt"
EN_COMBINED = REPO_ROOT / "languages/en/combined_en.txt"


def validate_glossary() -> None:
    """Bloque le build si les cellules terminologiques divergent du glossaire."""
    english = ability_table._parse_combined(EN_COMBINED)
    german = ability_table._parse_combined(DE_COMBINED)
    ability_by_english = {
        english[offset]: german[offset]
        for offset in german
        if offset in english
        and ability_table.ABILITY_TABLE_OFFSET <= offset <= ability_table.ABILITY_TABLE_LAST
    }
    for source, expected in terminology_section("ability_corrections").items():
        if ability_by_english.get(source) != expected:
            raise ValueError(f"German ability {source!r} diverges from glossary")

    for raw_offset, cell in terminology_section("system_cells").items():
        offset = int(raw_offset, 16)
        if english.get(offset) != cell["english"] or german.get(offset) != cell["german"]:
            raise ValueError(f"German system cell {raw_offset} diverges from glossary")


def make_command(rom: Path) -> list[str]:
    validate_glossary()
    return build_command(
        "patch_ability_names_fr.py",
        rom,
        combined=DE_COMBINED,
        combined_en=EN_COMBINED,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    return run(make_command(args.rom))


if __name__ == "__main__":
    raise SystemExit(main())
