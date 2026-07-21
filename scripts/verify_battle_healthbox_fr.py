#!/usr/bin/env python3
"""Verify in-emulator that the in-battle healthbox label renders « PV », not « HP ».

Consumes the OBJ VRAM dump produced by ``scripts/probe_battle_healthbox_fr.mts``
(which continues the rattata_levelup save, farms a REAL wild encounter and dumps
OBJ VRAM once a healthbox label tile is on screen), then checks the live tiles
against the authoritative « HP »/« PV » art from ``patch_hp_labels_fr``:

  * at least one « V » letter tile (unique to « PV ») MUST be present  → PV rendered;
  * no « H » letter tile (unique to « HP ») may be present            → no stale HP.

This is the end-to-end proof issue #125 was missing: the ROM-byte tests show the
four LZ77 blocks *decode* to PV, and this shows the battle engine actually *loads*
one of them into OBJ VRAM in a live fight.

Run::

    python3 scripts/battle_hp_label_tiles.py > <dumpdir>/label_tiles.json
    tsx     scripts/probe_battle_healthbox_fr.mts <rom> <dumpdir>
    python3 scripts/verify_battle_healthbox_fr.py <dumpdir>
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scripts.battle_hp_label_tiles import label_tiles  # noqa: E402

TILE = 32
DEFAULT_DUMP = ROOT_DIR / "output" / "proofs" / "battle-healthbox"


def _tile_present(vram: bytes, tile_hex: str) -> bool:
    want = bytes.fromhex(tile_hex)
    for off in range(0, len(vram) - TILE + 1, TILE):
        if vram[off:off + TILE] == want:
            return True
    return False


def verify(dump_dir: Path) -> tuple[bool, list[str]]:
    obj = dump_dir / "battle-vram-obj.bin"
    msgs: list[str] = []
    if not obj.exists():
        return False, [f"missing OBJ VRAM dump {obj} — run probe_battle_healthbox_fr.mts first"]
    vram = obj.read_bytes()
    tiles = label_tiles()

    pv_found = [h for h in tiles["pv_v"] if _tile_present(vram, h)]
    hp_found = [h for h in tiles["hp_h"] if _tile_present(vram, h)]

    ok = bool(pv_found) and not hp_found
    if pv_found:
        msgs.append(f"« PV » healthbox label present in OBJ VRAM ({len(pv_found)} « V » tile variant(s))")
    else:
        msgs.append("FAIL: no « V » tile found — healthbox does not render « PV »")
    if hp_found:
        msgs.append(f"FAIL: stale « HP » label still present ({len(hp_found)} « H » tile variant(s))")
    else:
        msgs.append("no « H » tile found — « HP » is gone")
    return ok, msgs


def main() -> int:
    dump_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DUMP
    ok, msgs = verify(dump_dir)
    for m in msgs:
        print(("PASS: " if ok and not m.startswith(("FAIL", "no «")) else "") + m)
    print("verify_battle_healthbox_fr:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
