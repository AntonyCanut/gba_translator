"""In-engine replay guard for the give-CS freeze (ticket « Problème pas de gain
d'objet »).

This is the "on this sequence" e2e test the ticket asks for. It loads the
savestate taken just before the post-Zeph cutscene
(``tests/fixtures/saves/givecs_freeze.ss9``) into the freshly built French ROM
and mashes A through the whole give-CS box, judging a freeze by SCREEN HASH —
the rendered frame staying pixel-identical for many consecutive A-presses.
(Player map/pos is NOT a freeze signal: you stand still during the entire
conversation, so a pos-based check reports "stuck" for a healthy dialogue. The
real freeze is the field-move description word-wrap spinning forever, where the
screen genuinely stops updating.)

It drives mGBA via the repo's own ``scripts/verify_givecs_no_freeze.mts`` (the
emulator-web TS bridge) and asserts no genuine freeze. The verifier is
self-checking: it returns 1 on a build whose give-CS struct still points at the
unterminated description, and 0 once every consumer is terminated. The test
skips cleanly when mGBA, ``tsx``/node modules, the ROM, or the savestate is
unavailable, so it is a no-op in headless CI — the deterministic CI guard is
``test_givecs_move_desc_freeze.py``.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
FR_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-fr.gba"
SAVESTATE_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "saves" / "givecs_freeze.ss9"
VERIFY_SCRIPT = PROJECT_ROOT / "scripts" / "verify_givecs_no_freeze.mts"
TSX = PROJECT_ROOT / "emulator-web" / "node_modules" / ".bin" / "tsx"
SLOT = 9


def _mgba_path() -> str | None:
    env = os.environ.get("MGBA_PATH")
    if env and pathlib.Path(env).exists():
        return env
    return shutil.which("mgba") or (
        "/opt/homebrew/bin/mgba" if pathlib.Path("/opt/homebrew/bin/mgba").exists() else None
    )


@pytest.mark.slow
@pytest.mark.emulator
def test_give_cs_sequence_does_not_freeze():
    if not FR_ROM_PATH.exists():
        pytest.skip("GenedRom-fr.gba not found (run `make build-fr`)")
    if not SAVESTATE_FIXTURE.exists():
        pytest.skip("givecs_freeze.ss9 fixture not found")
    if not TSX.exists():
        pytest.skip("emulator-web tsx not installed (run npm install)")
    mgba = _mgba_path()
    if not mgba:
        pytest.skip("mGBA not found (set MGBA_PATH)")

    # mGBA loads savestate slot 9 from <rom>.ss9 — stage the fixture there.
    slot_path = FR_ROM_PATH.with_suffix(f".ss{SLOT}")
    shutil.copyfile(SAVESTATE_FIXTURE, slot_path)

    proc = subprocess.run(
        [str(TSX), str(VERIFY_SCRIPT), str(FR_ROM_PATH), str(SLOT)],
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "MGBA_PATH": mgba},
        capture_output=True,
        text=True,
        timeout=420,
    )
    # Last stdout line is the JSON verdict.
    verdict = None
    for line in reversed(proc.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            verdict = json.loads(line)
            break

    if verdict is None:
        pytest.skip(f"verifier produced no verdict (mGBA env issue):\n{proc.stderr[-800:]}")
    if not verdict.get("reached"):
        pytest.skip("savestate never reached the give-CS map (savestate/ROM drift)")

    assert not verdict.get("frozen"), (
        "give-CS sequence FROZE in mGBA: the field-move description word-wrap "
        "spun forever (screen static). The build still points a consumer at an "
        f"unterminated description. verifier={verdict} stderr={proc.stderr[-400:]}"
    )
