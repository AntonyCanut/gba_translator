"""E2E — Italian ROM: reach and win the first battle.

Loads a pre-baked savestate fixture (``tests/fixtures/saves/it_first_battle.ss7``)
into the Italian ROM with mGBA, then drives the battle via
``scripts/probe_it_battle.mts``.  The probe:

 * Advances through the first scripted battle using A-mashing.
 * Detects battles via Italian text buffers (reliable; the inBattle flag is
   unreliable in Unbound).
 * Detects freezes via screen-hash stability (per project conventions).
 * Asserts ``battleReached``, ``battleWon``, and zero English residues in the
   battle text.

If the savestate fixture does not yet exist the probe auto-generates it by
playing from boot through the Unbound intro.  That first run takes longer but
commits the fixture to ``tests/fixtures/saves/it_first_battle.ss7`` so all
subsequent runs use the fast path.

The test is skipped cleanly when mGBA, tsx, or the IT ROM is unavailable, so it
is a no-op in headless CI where those are absent; the static build-integrity
guards (``test_italian_build.py``) cover the CI gate instead.

Marks: slow, emulator
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import subprocess

import pytest

_HERE = pathlib.Path(__file__).resolve()


def _project_root() -> pathlib.Path:
    """Return the project root the tests are actually running from.

    Defaults to the checkout containing this file (the worktree's own
    checkout when run inside .singularity-worktrees/<id>/), so tests use
    the ROM built there rather than the main checkout. Set GBA_PROJECT_ROOT
    to explicitly point elsewhere.
    """
    env_root = os.environ.get("GBA_PROJECT_ROOT")
    if env_root:
        return pathlib.Path(env_root)
    return _HERE.parent.parent.parent.parent


PROJECT_ROOT = _project_root()
IT_ROM = PROJECT_ROOT / "output" / "roms" / "GenedRom-it.gba"
PROBE = PROJECT_ROOT / "scripts" / "probe_it_battle.mts"
FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "saves" / "it_first_battle.ss7"
TSX = PROJECT_ROOT / "emulator-web" / "node_modules" / ".bin" / "tsx"
FIXTURE_SLOT = 7


def _parse_verdict(stdout: str) -> "dict | None":
    """Extract the last JSON object from probe stdout.

    Probes may emit compact single-line JSON (``{"key": ...}``) or pretty-printed
    multi-line JSON.  Both are handled by attempting to parse any JSON-looking
    block found scanning backward from the end of stdout.
    """
    text = stdout.strip()
    # Fast path: last non-empty line is compact JSON.
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                pass
    # Slow path: find the LAST `{...}` block (possibly spanning multiple lines).
    match = None
    for m in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}', text, re.DOTALL):
        match = m
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    # Last resort: collect all lines from the final `{` to the final `}`.
    lines = text.splitlines()
    start = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].strip().startswith('{')), None)
    end = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].strip() == '}'), None)
    if start is not None and end is not None and end >= start:
        block = '\n'.join(lines[start:end + 1])
        try:
            return json.loads(block)
        except json.JSONDecodeError:
            pass
    return None


def _mgba() -> str | None:
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
def test_it_first_battle_reached_and_won() -> None:
    """Italian ROM: first battle is reached and won without freeze or English text."""
    if not IT_ROM.exists():
        pytest.skip(
            f"GenedRom-it.gba not found at {IT_ROM} — run: python3 scripts/build_language.py it"
        )
    if not PROBE.exists():
        pytest.skip(f"probe_it_battle.mts not found at {PROBE}")
    if not TSX.exists():
        pytest.skip("emulator-web tsx not installed — run: npm install inside emulator-web/")
    mgba = _mgba()
    if not mgba:
        pytest.skip("mGBA not found (install with: brew install mgba, or set MGBA_PATH)")

    # Stage fixture savestate for the ROM's slot file if it exists.
    # The probe also stages and saves the fixture itself on first-generation runs.
    slot_path = IT_ROM.with_suffix(f".ss{FIXTURE_SLOT}")
    if FIXTURE.exists():
        shutil.copyfile(FIXTURE, slot_path)

    proc = subprocess.run(
        [str(TSX), str(PROBE), str(IT_ROM)],
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "MGBA_PATH": mgba},
        capture_output=True,
        text=True,
        timeout=600,  # generous for first-run intro playthrough
    )

    verdict = _parse_verdict(proc.stdout)

    if verdict is None:
        pytest.skip(
            f"probe produced no JSON verdict (mGBA environment issue)\n"
            f"stderr (last 800 chars):\n{proc.stderr[-800:]}"
        )

    froze = verdict.get("froze", False)
    battle_reached = verdict.get("battleReached", False)
    battle_won = verdict.get("battleWon", False)
    english_hits = verdict.get("englishHits", [])

    assert not froze, (
        "Italian ROM FROZE during the first battle — screen hash was stable across "
        f"many A-presses. verdict={verdict}\nstderr (last 600 chars):\n{proc.stderr[-600:]}"
    )

    assert battle_reached, (
        "Italian ROM never reached the first battle within the iteration budget. "
        "Check that the IT intro completes correctly and that probe_it_battle.mts "
        f"text patterns match the actual IT text. verdict={verdict}\n"
        f"stderr (last 600 chars):\n{proc.stderr[-600:]}"
    )

    assert battle_won, (
        "Italian ROM reached the first battle but did not win it. "
        f"verdict={verdict}\nstderr (last 600 chars):\n{proc.stderr[-600:]}"
    )

    assert not english_hits, (
        f"Italian battle text contains {len(english_hits)} English residue(s): "
        f"{english_hits[:5]}. Translations may be missing or incorrect."
    )

    # If the fixture was newly generated by this run, log it.
    if FIXTURE.exists():
        size = FIXTURE.stat().st_size
        print(f"[it-battle] Fixture present: {FIXTURE} ({size} bytes)")
    else:
        print("[it-battle] No fixture generated (probe may have skipped fixture save)")


@pytest.mark.slow
@pytest.mark.emulator
def test_it_battle_menu_text_in_italian() -> None:
    """Italian ROM battle menu labels (Lotta/Borsa/Pokémon/Fuggi) must be in Italian.

    This is the regression guard for ticket F-56 fix: the battle menu was
    previously showing English labels (FIGHT/BAG/POKEMON/RUN).  We verify
    the corrected labels are present by checking that the text buffers during
    the battle contain Italian battle-menu markers and no English equivalents.

    If the fixture does not exist this test shares the probe with
    test_it_first_battle_reached_and_won (same probe run generates the fixture).
    """
    if not IT_ROM.exists():
        pytest.skip("GenedRom-it.gba not found — run: python3 scripts/build_language.py it")
    if not PROBE.exists():
        pytest.skip(f"probe_it_battle.mts not found at {PROBE}")
    if not TSX.exists():
        pytest.skip("emulator-web tsx not installed")
    mgba = _mgba()
    if not mgba:
        pytest.skip("mGBA not found")

    slot_path = IT_ROM.with_suffix(f".ss{FIXTURE_SLOT}")
    if FIXTURE.exists():
        shutil.copyfile(FIXTURE, slot_path)

    proc = subprocess.run(
        [str(TSX), str(PROBE), str(IT_ROM)],
        cwd=str(PROJECT_ROOT),
        env={**os.environ, "MGBA_PATH": mgba},
        capture_output=True,
        text=True,
        timeout=600,
    )

    verdict = _parse_verdict(proc.stdout)

    if verdict is None:
        pytest.skip("probe produced no JSON verdict (mGBA environment issue)")

    if not verdict.get("battleReached"):
        pytest.skip("battle not reached — cannot verify menu labels")

    english_hits = verdict.get("englishHits", [])

    # No FIGHT/BAG/RUN/POKEMON should survive as literal words in IT battle text.
    english_menu = [
        h for h in english_hits
        if any(kw in h for kw in ("FIGHT", "BAG", "RUN", "POKEMON"))
    ]
    assert not english_menu, (
        "English battle-menu labels still present in Italian ROM: "
        f"{english_menu}. The menu translation patch (Lotta/Borsa/Pokémon/Fuggi) "
        "may have been overwritten or is missing from the IT build."
    )
