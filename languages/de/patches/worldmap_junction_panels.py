#!/usr/bin/env python3
"""German port of ``patch_worldmap_junction_panels_fr`` — translates the
arrow-prefixed World-Map junction panels the generic pipeline drops, sourcing
the German text from ``languages/de/combined_de.txt``.

Data-driven (``--source`` + ``--combined``); this wrapper only re-points the
French implementation at the German combined file. Panels still missing a
German entry in ``combined_de.txt`` stay English.

Free-space rationale: identical to ``mission_descriptions.py`` in this
directory — dispatched **without** ``--reference-rom`` (``reserved=None``) and
scheduled at the end of the DE patch list, so it harvests the EN-free /
ES-populated pool that the main-text relocation pass avoids. See that module's
docstring for the full explanation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from src.i18n.fr_patch_delegate import build_command, run  # noqa: E402

DE_COMBINED = REPO_ROOT / "languages/de/combined_de.txt"


def make_command(rom: Path) -> list[str]:
    # reference_rom omitted on purpose (reserved=None) — see the free-space
    # rationale in languages/de/patches/mission_descriptions.py.
    return build_command(
        "patch_worldmap_junction_panels_fr.py",
        rom,
        source=True,
        combined=DE_COMBINED,
        reference_rom=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    return run(make_command(args.rom))


if __name__ == "__main__":
    raise SystemExit(main())
