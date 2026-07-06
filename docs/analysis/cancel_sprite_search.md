# Locating the "Cancel" (ANNUL.) button sprite — analysis (F-108 → F-111)

## TL;DR

The "Cancel 32x16.bmp" button sprite could **not** be located, and the
investigation shows *why every prior attempt stalled*: the guiding hypothesis
was wrong. The Cancel button is **not** on the player/rival naming keyboard
**nor** on the Pokémon nickname screen — the three F‑108 sprites come from
**three unrelated screens**. Blind mGBA navigation toward the starter/nickname
flow (F‑109, F‑110) was therefore chasing a screen that never shows this
button.

A dependency‑free static ROM sprite scanner was built
(`scripts/scan_sprite_region.py`) so future work no longer needs the emulator
to inspect candidate graphics. Using it, the Cancel button was ruled out of the
UI OBJ‑graphics regions in every plausible static storage layout.

**The one missing fact that unblocks this ticket: on which in‑game screen does
the graphical "Cancel" button actually appear?** That is user knowledge (they
authored the `.bmp` and have seen the button); it is not derivable from the
code, because no Unbound decomp source exists in this repo.

## What was proven

### 1. The three F‑108 sprites are three unrelated screens

| BMP | Screen | Status |
|-----|--------|--------|
| `Selection 40x104.bmp` | naming keyboard (right‑side help panel) | located in F‑109 (`0x00E985D8`, raw/uncompressed, 5×13 tiles) |
| `Afflictions 32x64.bmp` | battle status badges | already known = `status_badges` |
| `Cancel 32x16.bmp` | **unknown screen** | not located |

They are **not** three sprites from one screen. Nothing forces the Cancel
button to live near the naming keyboard.

### 2. The naming keyboard has no Cancel — verified visually

Rendering the whole `selection` sheet (`scan_sprite_region.py render
0x00E985D8 --tiles-wide 5 --count 65`) shows the complete label pool:

```
[blank swatch]   SELECT ▷
BACK             B BUTTON        OK        START ▷
UPPER            lower           others
```

Those 65 tiles are the entire pool the naming engine DMAs from. There is **no
CANCEL / ANNUL. label anywhere in it.** (Side note: in the currently‑built
`output/roms/GenedRom-fr.gba` these labels are still **English** — F‑109's
`selection` FR patch is not present in that build, so a rebuild is needed
before the naming panel shows French. Tracked separately; not this ticket.)

### 3. Cancel is not an uncompressed 4×2 "text button" in the UI regions

A full‑ROM structural scan for the exact layout of the supplied `.bmp` (≥4
uniform background rows on top, ≥3 on the bottom, uniform side margins, a
text band spanning most of the 32 px width) returns only decorative sprite
fragments and main‑text‑region false positives (e.g. `0x1F4A60` is inside the
`0x1F00000` dialogue region). No CANCEL.

### 4. Cancel is not an LZ77 "text button" in the UI regions either

Decompressing every plausible LZ77 block in `0x00800000–0x00F00000` (2354
blocks) and re‑scanning yields only solid horizontal gradient/bar tiles (HP
bars, shadows, terrain) — continuous ink with no inter‑letter gaps, i.e. not
text.

## Why the static search can't finish the job alone

* **No border to anchor on.** The `.bmp` is flat text (background = palette
  index 1, glyphs = indices 2 & 5) with no box frame, so there is no
  distinctive shape to byte‑match.
* **EN ≠ FR.** The ROM holds the *English* "CANCEL"; the supplied `.bmp` is the
  *French* "ANNUL.". Their pixels differ across the whole text band, so a raw
  `rom.find(tile_bytes)` of the FR art cannot match the EN original.
* **Unknown layout.** If Cancel is one label packed inside a larger multi‑label
  sheet (like the naming pool), there is no blank top margin to key on, and the
  looser "reads‑like‑text" scan drowns in ROM noise (17 k+ hits).
* **Possibly not a sprite at all.** Many FRLG button labels (e.g. the party
  menu "CANCEL") are drawn by the text/window engine, not stored as OBJ tiles.
  If that is the case here, the fix is a *font/text* change, not a sprite
  insert — which again depends on identifying the screen.

## The new tool: `scripts/scan_sprite_region.py`

Reusable for this and any future "find a UI sprite in the ROM" ticket, with
**no emulator and no third‑party deps** (stdlib + the existing LZ77/tile
helpers in `languages/fr/patches/font.py`).

```bash
# inspect a known raw sprite (any byte offset, not just tile‑aligned):
python3 scripts/scan_sprite_region.py render 0x00E985D8 --tiles-wide 5 --count 65 -o /tmp/sel.bmp

# hunt margin‑framed text buttons across a region (raw + every LZ77 block):
python3 scripts/scan_sprite_region.py buttons --start 0x00E00000 --end 0x00F00000 -o /tmp/cands.bmp

# looser "reads like text" scan (for labels packed in a bigger sheet):
python3 scripts/scan_sprite_region.py text --start 0x00E80000 --end 0x00EA0000 -o /tmp/txt.bmp

# .bmp → .png (macOS): sips -s format png /tmp/cands.bmp --out /tmp/cands.png
```

## Recommended next step (fastest path to done)

1. **Ask the user which screen shows the graphical "Cancel" button.** One
   sentence unblocks everything (candidates worth confirming: party‑menu action
   button, PC/storage, Mystery Gift, a custom Unbound menu). This avoids a 5th
   ticket of blind maze‑walking.
2. Reach that specific screen in mGBA (usually far easier than the
   starter/nickname flow — e.g. the party menu needs only one Pokémon), dump
   OBJ VRAM + OAM **synchronised in the same call** as the screenshot (the
   F‑109 trap), and read back the tile bytes actually on screen.
3. `rom.find(<those EN tile bytes>)` → offset. If it does not resolve to a
   static block, the label is text‑engine‑drawn and the task becomes a
   font/text fix instead of a sprite insert.
4. Once the offset is known, the insert path already exists on the F‑110
   branch (`languages/fr/sprites.py` + `scripts/insert_sprite.py`, add a
   `cancel` entry). Confirm whether that block is raw or LZ77 with
   `scan_sprite_region.py render … [--lz]` first.
