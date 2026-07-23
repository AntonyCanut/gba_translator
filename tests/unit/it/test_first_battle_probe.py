"""Gardes statiques de la sonde du premier combat italien."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "fixtures" / "saves" / "it_first_battle.ss7"
ROUTE = ROOT / "tests" / "fixtures" / "routes" / "it_first_battle.json"
PROBE = ROOT / "scripts" / "probe_it_battle.mts"


def test_first_battle_savestate_is_versioned_mgba_state() -> None:
    """La sonde doit démarrer d'une vraie savestate mGBA courte et versionnée."""
    data = FIXTURE.read_bytes()

    assert len(data) > 4_096
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"gbAs" in data


def test_first_battle_route_is_explicit_and_consumed_by_probe() -> None:
    """La route depuis la fixture doit être déclarative, bornée et utilisée."""
    route = json.loads(ROUTE.read_text(encoding="utf-8"))
    source = PROBE.read_text(encoding="utf-8")

    assert route["start"]["map"] == [4, 10]
    assert all(isinstance(value, int) for value in route["start"]["position"])
    assert 1 <= len(route["steps"]) <= 32
    assert all(step["key"] in {"A", "B", "UP", "DOWN", "LEFT", "RIGHT"} for step in route["steps"])
    assert all(1 <= step["repeat"] <= 120 for step in route["steps"])
    assert all(1 <= step["holdFrames"] <= 12 for step in route["steps"])
    assert all(1 <= step["frames"] <= 120 for step in route["steps"])
    assert "it_first_battle.json" in source
    assert "followRoute" in source
