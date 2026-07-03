#!/usr/bin/env python3
"""Italian delegation of ``patch_battle_string_templates_fr`` — restores the
in-battle defeat-speech / switch-out battle-string templates from the pristine
English ROM.

This patch is language-agnostic: it repairs the ``{FD24}`` timed control-code
cluster the builder corrupts, injecting no localized text. The Italian build runs
exactly the same repair, so this wrapper simply re-invokes it with ``--source``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.i18n.fr_patch_delegate import build_command, run  # noqa: E402


def make_command(rom: Path) -> list[str]:
    return build_command("patch_battle_string_templates_fr.py", rom, source=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    args = parser.parse_args(argv)
    return run(make_command(args.rom))


if __name__ == "__main__":
    raise SystemExit(main())
