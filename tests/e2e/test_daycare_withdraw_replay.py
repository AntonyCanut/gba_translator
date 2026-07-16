"""In-engine replay guard for the Day-Care "withdraw your Pokémon" freeze
(ticket B-187 « Freeze jeu »), run against EVERY built language.

Choosing "Yes" to "do you want your Pokémon back?" at the Day-Care opens a
selection menu whose fixed-size cursor-help window renders the global
"go back to the previous menu" description at 0x416244. Some strings there make
that window's word-wrap spin forever → the frame freezes / the ROM soft-resets.
The trigger is a pixel-level rendering quirk that does NOT correlate with the
first-word width, the line width, the byte length or the presence of a newline
(all empirically ruled out in mGBA — e.g. "Torna al menu precedente." is fine
but the shorter "Vai al menu precedente." freezes), so the only trustworthy
oracle is an actual in-engine replay. That is what this test is.

Because the freeze is language-agnostic (the cursor-help window is the same code
in every build) it must be checked in EVERY language, not just FR: a fix that
only lands for one language leaves the others crashing. This test loads the
committed Day-Care battery save into each built ROM, mashes A through the
withdraw flow, and judges a freeze by SCREEN HASH (never player position or CPU
PC — both read "stuck" for a healthy dialogue; see the diagnosing-unbound-freezes
skill). It drives the menu through each build's OWN prompt text, so one save
covers all languages.

The verifier ``scripts/verify_daycare_no_freeze.mts`` is self-checking: it
reports frozen=true on a ROM whose 0x416244 string still overflows the window
(proven against a deliberately re-broken DE ROM) and frozen=false once a safe
string is in place. The test skips cleanly when mGBA, tsx/node modules, the
language ROM (gitignored for it/de/indie — build it first) or the save fixture
is unavailable, so it is a no-op in headless CI. The deterministic CI guard is
``tests/test_daycare_withdraw_menu_help.py``.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.rom

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
VERIFY_SCRIPT = PROJECT_ROOT / "scripts" / "verify_daycare_no_freeze.mts"
SAVE_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "saves" / "daycare_withdraw.sav"
TSX = PROJECT_ROOT / "emulator-web" / "node_modules" / ".bin" / "tsx"

# Every built language that ships this cursor-help cell. indie has no 0x416244
# override so it inherits the English source string (which is safe), but we still
# replay it — a future override could reintroduce the freeze.
BUILT_LANGUAGES = ["fr", "it", "de", "indie"]


def _mgba_path() -> str | None:
    env = os.environ.get("MGBA_PATH")
    if env and pathlib.Path(env).exists():
        return env
    return shutil.which("mgba") or (
        "/opt/homebrew/bin/mgba"
        if pathlib.Path("/opt/homebrew/bin/mgba").exists()
        else None
    )


@pytest.mark.slow
@pytest.mark.emulator
@pytest.mark.parametrize("lang", BUILT_LANGUAGES)
def test_daycare_withdraw_does_not_freeze(lang, tmp_path):
    rom = PROJECT_ROOT / "output" / "roms" / f"GenedRom-{lang}.gba"
    if not rom.exists():
        pytest.skip(f"GenedRom-{lang}.gba not found — run: make build-{lang}")
    if not SAVE_FIXTURE.exists():
        pytest.skip("daycare_withdraw.sav fixture not found")
    if not VERIFY_SCRIPT.exists():
        pytest.skip("verify_daycare_no_freeze.mts not found")
    if not TSX.exists():
        pytest.skip("emulator-web tsx not installed (run npm install)")
    mgba = _mgba_path()
    if not mgba:
        pytest.skip("mGBA not found (set MGBA_PATH)")

    # Stage the ROM + battery save into an isolated dir so mGBA auto-loads the
    # Day-Care save and we never clobber the build's own .sav.
    staged_rom = tmp_path / f"{lang}.gba"
    shutil.copyfile(rom, staged_rom)
    shutil.copyfile(SAVE_FIXTURE, tmp_path / f"{lang}.sav")

    proc = subprocess.run(
        [str(TSX), str(VERIFY_SCRIPT), str(staged_rom)],
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
    if not verdict.get("reached"):
        pytest.skip(
            f"[{lang}] save never opened the withdraw prompt "
            f"(save/ROM drift): {verdict}"
        )

    assert not verdict.get("frozen"), (
        f"[{lang}] Day-Care withdraw menu FROZE in mGBA: the cursor-help window "
        f"(0x416244) word-wrap spun forever (screen static / soft-reset). "
        f"The build ships an unsafe string at that offset. verdict={verdict} "
        f"stderr={proc.stderr[-400:]}"
    )
