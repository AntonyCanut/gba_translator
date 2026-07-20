---
name: unbound-dexnav-header-graphics-custom-asset
description: "DexNav column headers (SEARCH LEVEL/METHOD/HIDDEN ABILITY/HELD ITEMS) are baked into an Unbound-specific, non-public background asset — how it was located and patched"
metadata:
  node_type: memory
  type: project
  originSessionId: f7d5cb0d-58ef-4915-adea-40703806c64d
---

Unbound's DexNav screen draws its own **custom** background
(`DexNavBGUnboundTiles`/`Map`/`Pal` in CFRU's `src/dexnav.c`, guarded by
`#ifdef UNBOUND`) — this asset is **not** in the public
`Skeli789/Complete-Fire-Red-Upgrade` repo (only the vanilla `DexNavBG.png` is
public, and it has a completely different layout/palette). Don't waste time
matching the generic CFRU asset against the ROM — it was checked and does
not match.

**How the real block was found (no live emulator needed in the end):**
1. Got a real in-game screenshot of the DexNav screen (ticket attachment) to
   sample actual RGB colours of the banner/text/body.
2. Quantized those RGB samples to GBA 15-bit colours (5 bits/channel) and did
   an exact-value search (±1 tolerance) for a 2-byte-aligned window in the
   ROM containing 3+ of those colours close together → found the raw,
   **uncompressed** 32-byte (16-colour) palette at `0x00B1560A` in
   `output/roms/GenedRom-fr.gba`.
3. Scanned backward from there for valid LZ77 blocks: the linker placed
   `tiles`/`map`/`palette` contiguously in source-declaration order, so the
   tileset and tilemap sit immediately before the palette with **zero gap**.
   Tileset: `0x00B14FA0` (134 tiles / 4288 bytes decompressed, compressed
   1176 bytes). Tilemap: `0x00B15438` (32×20 screen entries / 1280 bytes,
   canvas is 32 tiles wide though only 30 are visible on screen — matches
   grit's `-aw256` flag). Tileset compressed end == tilemap start exactly.
4. Rendered tileset+map+palette in Python to confirm visually before writing
   any patch (see script for the decode).

**Consequence for patching:** since tileset and tilemap are back-to-back
with **no padding**, a recompressed tileset must never exceed its original
compressed length (1176 bytes) — there's no tolerance window like
`patch_hp_labels_fr.py`'s padding-tail check. French replacement text had to
be trimmed/abbreviated ("NIVEAU RECH", "METHODE", "TALENT CACHE", "OBJETS")
to keep the recompressed tileset ≤ 1176 bytes — LZ77 size is NOT monotonic
with text length (shorter text can compress *worse* depending on how it
breaks up repeated runs), so this must be verified empirically per candidate
string, not assumed.

Each header occupies its own **dedicated, non-shared** tile range (confirmed
by diffing all 4 header's tile-id lists against each other); only a couple
of blank "filler"/"cap" tiles are reused across rows, and those are never
touched. Letter pixels live in tile rows 2-7 only; rows 0-1 are a per-tile
decorative top divider that must be preserved untouched.

Fix: `scripts/patch_dexnav_headers_fr.py` in `gba_translator`, wired into
`make build-fr` right after `patch_type_icons_fr.py`. Test:
`tests/test_patch_dexnav_headers_fr.py`. See also
[[unbound-hp-pv-label-graphics-blocks]] and [[unbound-type-icons-are-graphics]]
for the sibling LZ77-graphics-patch pattern this follows.
