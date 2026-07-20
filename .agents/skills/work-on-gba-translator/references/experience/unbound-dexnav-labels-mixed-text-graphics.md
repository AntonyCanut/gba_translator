---
name: unbound-dexnav-labels-mixed-text-graphics
description: DexNav screen labels are split between pointer-text (fixed via combined_fr.txt) and a baked-in background graphic — how to tell which is which using the CFRU GitHub source
metadata:
  node_type: memory
  type: project
  originSessionId: 3522c4d8-480e-47f4-b9e1-5fc6b4261357
---

The DexNav screen (route encounter tracker) mixes two mechanisms for its labels — don't
assume the whole screen is one class.

**Pointer text (class 1, fixable via `combined_fr.txt`)**: habitat tabs "Water"/"Land",
terrain names (Sand/Reeds/Magma/flower colors), encounter methods (Walk/Surf/Old Rod/…),
"Chain: ", "Swarm", "Unavailable", "Register"/"Scan"/"Cancel". Cluster lives at
`0xA439B0`–`0xA43ACD` in `englishrom.gba` (right after a debug/cheat-menu string block at
`0xA438EF`–`0xA439A4` — "Give Item"/"Level 100 Team"/"Max Coinage"/etc — which is a
**different, unrelated feature** and was deliberately left out of scope). Fixed in
gba_translator commit `dc05af0` (F-...ticket "Manque traduction DexNav" / B-151), verified
by tracing live pointers (`0x9D63xx`/`0x9D72xx`/`0x9D76xx`/`0xA69Axx` pointer sites →
decode target), not by reading the original offset directly (most of these strings grow in
French and get relocated by the reinserter — the original offset then holds either the
untouched EN bytes or something else entirely). Regression test:
`gba_translator/tests/test_dexnav_labels_combined_fr.py`.

**Graphic (class 2-like, NOT in any translation pass)**: the 4 column headers "SEARCH
LEVEL", "METHOD", "HIDDEN ABILITY", "HELD ITEMS" are baked as pixels, LZ77-compressed into
the ROM. No literal string exists in the ROM's CFRU-charmap encoding for these — confirmed
by encoding "SEARCH LEVEL"/"METHOD"/etc with `src/text/encoder.py` and finding zero matches
anywhere in `englishrom.gba`. Same class as TYPE/OT/ITEM word-images
([[unbound-summary-screen-labels]]) and HP/PS badges
([[unbound-hp-pv-label-graphics-blocks]]).

**Correction (F-71, resolved):** the generic CFRU `graphics/DexNav/DexNavBG.png` asset
guess above was **wrong** — Unbound uses its own custom, non-public
`DexNavBGUnboundTiles`/`Map`/`Pal` asset (see `#ifdef UNBOUND` branch in CFRU's
`src/dexnav.c`), completely different layout/palette from the public PNG. Locating and
patching the real ROM block required a different technique (real-screenshot colour
sampling, not the GitHub source) — see [[unbound-dexnav-header-graphics-custom-asset]] for
the full method and exact offsets. Fixed by `scripts/patch_dexnav_headers_fr.py` in
`gba_translator`.

**Reusable technique**: when a string search (`encode_string` + `bytes.find`) comes up
empty across the whole ROM for text that's clearly visible on screen, before assuming it's
unreachable/relocated, check whether it's baked into a **background graphic** instead.
Unbound is built on the open-source CFRU framework (`github.com/Skeli789/Complete-Fire-Red-Upgrade`) — `gh api search/code` / `gh api repos/.../contents/<path>` against that repo is a
fast way to confirm: grep the relevant `.c`/`.h` source for the literal string (e.g. window
templates in `include/new/dexnav_data.h`), and if it's a `.png` under `graphics/` instead of
a `gText_`/string literal, that confirms graphic-not-text before spending time on a fruitless
byte search in the ROM.
