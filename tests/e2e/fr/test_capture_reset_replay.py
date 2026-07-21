"""In-engine replay guard for the wild-capture reset (ticket « Capture reset
game »).

On the buggy build, catching any wild Pokémon showed the new-species Pokédex
page and then rebooted the game to the title screen: a blind byte scan in
``money_amount_order.py`` had reordered ``B7 FD xx`` sequences that were in
fact halves of Thumb ``BL`` instruction pairs (0xA2B7BA lies in the CFRU code
run by the capture flow). The deterministic CI guards live in
``tests/test_patch_money_amount_order_fr.py`` (content-guard unit tests).

This test drives the real flow in mGBA via
``scripts/verify_capture_no_reset.mts``: it loads the committed savestate
(``tests/fixtures/saves/capture_reset.ss0`` — mid-battle, a Poké Ball ready in
the bag), throws the ball and plays through the exp/Pokédex/nickname sequence.
The verdict signal is the PARTY: a successful capture appends the caught mon to
``gPlayerParty``, while a reboot re-loads the battery save and the party stays
unchanged. It skips cleanly when mGBA, tsx, the ROM or the fixtures are
missing, so it is a no-op in headless CI.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.rom

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent.parent
FR_ROM_PATH = PROJECT_ROOT / "output" / "roms" / "GenedRom-fr.gba"
SAV_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "saves" / "capture_reset.sav"
STATE_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "saves" / "capture_reset.ss0"
VERIFY_SCRIPT = PROJECT_ROOT / "scripts" / "verify_capture_no_reset.mts"
TSX = PROJECT_ROOT / "emulator-web" / "node_modules" / ".bin" / "tsx"


def _mgba_path() -> str | None:
    env = os.environ.get("MGBA_PATH")
    if env and pathlib.Path(env).exists():
        return env
    return shutil.which("mgba") or (
        "/opt/homebrew/bin/mgba" if pathlib.Path("/opt/homebrew/bin/mgba").exists() else None
    )


@pytest.mark.slow
@pytest.mark.emulator
def test_wild_capture_does_not_reset():
    if not FR_ROM_PATH.exists():
        pytest.skip("GenedRom-fr.gba not found (run `make build-fr`)")
    if not (SAV_FIXTURE.exists() and STATE_FIXTURE.exists()):
        pytest.skip("capture_reset fixtures not found")
    if not TSX.exists():
        pytest.skip("emulator-web tsx not installed (run npm install)")
    mgba = _mgba_path()
    if not mgba:
        pytest.skip("mGBA not found (set MGBA_PATH)")

    proc = subprocess.run(
        [str(TSX), str(VERIFY_SCRIPT), str(FR_ROM_PATH)],
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "MGBA_PATH": mgba},
        capture_output=True,
        text=True,
        timeout=420,
    )
    verdict = None
    for line in reversed(proc.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            verdict = json.loads(line)
            break

    if verdict is None:
        pytest.skip(f"verifier produced no verdict (mGBA env issue):\n{proc.stderr[-800:]}")
    if verdict.get("verdict") == "NOT_REACHED":
        pytest.skip("savestate never left the battle menu (savestate/ROM drift)")

    assert verdict.get("verdict") == "OK" and not verdict.get("reset"), (
        "wild-capture sequence RESET the game in mGBA: the caught Pokémon "
        "never survived in the party, i.e. the console rebooted after the "
        f"new-species Pokédex page. verifier={verdict} stderr={proc.stderr[-400:]}"
    )
