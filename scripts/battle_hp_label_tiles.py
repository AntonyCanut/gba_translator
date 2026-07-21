#!/usr/bin/env python3
"""Authoritative healthbox label tile signatures for issue #125.

The in-battle « HP »/« PV » label is a pair of 4bpp OBJ tiles decompressed
from one of the four healthbox LZ77 blocks (0xD1F604 / 0xEEF0AC / 0xEEF380 /
0xEEF688). ``patch_hp_labels_fr`` rewrites the letter rows so the pair reads
« PV » instead of « HP »:

    HP :  [ H ][ P ]        PV :  [ P ][ V ]
          h_tile p_tile           h_tile p_tile

The « H » letter is unique to HP and the « V » letter is unique to PV (the
« P » shape appears in both), so those two tiles are the unambiguous
discriminators when scanning live VRAM:

  * ``hp_h``  — the old « H » letter tiles: MUST be absent from battle VRAM;
  * ``pv_v``  — the new « V » letter tiles: at least one MUST be present.

``detect`` is the union of every label tile (H / P / V, old and new); its
presence means a healthbox label is on screen at all, i.e. we really are in a
rendered battle rather than looking at an unrelated frame.

Emits the three lists as JSON (hex tiles) so the JS mGBA probe can reuse the
exact same source of truth as the Python verifier.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from languages.fr.patches.hp_labels import (  # noqa: E402
    BATTLE_BLOCKS,
    BATTLE_H_TILE_HEX,
    BATTLE_P_TILE_HEX,
    HPEL_OLD_H_HEX,
    HPEL_OLD_P_HEX,
    _expected_new,
    _make_draw_battle_label,
    hpel_convert_pair,
)


def label_tiles() -> dict[str, list[str]]:
    hp_h: list[str] = []
    hp_p: list[str] = []
    pv_p: list[str] = []
    pv_v: list[str] = []
    for off, h_tile, p_tile in BATTLE_BLOCKS:
        old = {h_tile: BATTLE_H_TILE_HEX[off], p_tile: BATTLE_P_TILE_HEX[off]}
        new = _expected_new(old, _make_draw_battle_label(h_tile, p_tile))
        hp_h.append(old[h_tile].lower())      # old « H »  (unique to HP)
        hp_p.append(old[p_tile].lower())      # old « P »  (HP's second letter)
        pv_p.append(new[h_tile].lower())      # new « P »  (PV's first letter)
        pv_v.append(new[p_tile].lower())      # new « V »  (unique to PV)

    # Opponent healthbox (uncompressed element): old « H » must vanish, new « V »
    # must appear. This is the tile the 2.1.68 build still rendered as « HP ».
    new_h, new_p = hpel_convert_pair(
        bytes.fromhex(HPEL_OLD_H_HEX), bytes.fromhex(HPEL_OLD_P_HEX))
    hp_h.append(HPEL_OLD_H_HEX.lower())       # opponent old « H »  (unique to HP)
    hp_p.append(HPEL_OLD_P_HEX.lower())       # opponent old « P »
    pv_p.append(new_h.hex().lower())          # opponent new « P »
    pv_v.append(new_p.hex().lower())          # opponent new « V »  (unique to PV)

    detect = sorted(set(hp_h + hp_p + pv_p + pv_v))
    return {"hp_h": hp_h, "hp_p": hp_p, "pv_p": pv_p, "pv_v": pv_v, "detect": detect}


if __name__ == "__main__":
    print(json.dumps(label_tiles(), indent=2))
