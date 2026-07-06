#!/usr/bin/env python3
"""German port of ``patch_mission_descriptions_fr`` — writes the bounty-mission
descriptions exactly, in their 3-line layout, sourcing the German text from
``languages/de/combined_de.txt``.

Data-driven (``--source`` + ``--combined``); this wrapper only re-points the
French implementation at the German combined file. Missions still missing a
German entry in ``combined_de.txt`` stay English.

Free-space rationale
---------------------
The relocation this patch performs used to abort with ``0/47 FAILED (free
space)`` in the packed German build. That was **not** a shortage of free space
in the ROM — it was the ``--reference-rom`` flag.

The generic builder (``19_build_translated_rom_generic``) relocates the verbose
German main text with the Spanish ROM passed as ``--pointer-proof-rom``, which
also makes its :class:`FreeSpaceAllocator` treat every Spanish-populated byte as
off-limits (the FR inline-mirror pass would otherwise clobber a string relocated
there). German text is long, so the main pass consumes essentially the whole
``EN-free ∩ ES-free`` pool (~901 KB), leaving ~0 bytes that are free in *both*
ROMs. A post-build patch that also excludes Spanish-populated bytes (via
``--reference-rom``) therefore finds nothing and fails outright — this is the
blocker recorded as ``unbound-generic-build-freespace-blocks-relocation``.

But there is ~29 KB of space that is free in English yet populated in Spanish,
which the main pass deliberately *avoids* and never touches. This wrapper runs
at the very end of the DE patch list — after the ``inline`` mirror pass and
every other relocation — so nothing writes to those bytes afterwards. It can
therefore safely harvest that otherwise-wasted pool by dispatching **without**
``--reference-rom`` (``reserved=None``), which relocates all 47 missions with no
cost to main-text coverage. See ``src/core/text_reinserter.FreeSpaceAllocator``.
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
    # reference_rom is intentionally omitted (reserved=None): see the module
    # docstring — the packed DE build has no EN∩ES-free space left, so the patch
    # harvests the EN-free/ES-populated pool the main pass avoids instead.
    return build_command(
        "patch_mission_descriptions_fr.py",
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
