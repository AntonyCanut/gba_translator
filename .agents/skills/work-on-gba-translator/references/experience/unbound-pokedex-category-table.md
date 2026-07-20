---
name: unbound-pokedex-category-table
description: "Pokédex species category (\"Mouse Pokémon\") real table, render routine, and FR \"Pokémon <noun>\" reorder"
metadata:
  node_type: memory
  type: project
  originSessionId: ee45431e-bc9a-4b51-9c3b-a13964e935db
---

Pokédex species **category** (the "Mouse"/"Souris" word, distinct from the long dex
paragraph in [[unbound-pokedex-entries]]).

- **Real table the engine reads:** base `0x1A357CC`, stride 36, indexed by **National
  Dex number**, text at record start (+0x00), **capped at 11 chars** (the render copy
  loop at `0x10585A` `cmp r4,#0xa`). Numeric height/weight/scale fields begin at **+0x0C**;
  the description-pointer table (`0x1A35800`, used by `src/core/pokedex.py`) is interleaved
  into the record tails → **only write +0x00..+0x0B** (11 bytes + 0xFF terminator).
- Lookup: `0x965bbf4` returns `index*36 + 0x081A357CC`. Verified: idx1=Bulbasaur "Seed",
  idx4=Charmander "Lizard", idx25=Pikachu "Mouse".
- **TRAP:** the category entries in `combined_fr.txt` (offsets like `0x1A35812`) are **2 bytes
  early into a different table view** and silently never render. Don't fix categories there.
- **Render routine `0x105800`:** copies category → buffer, prints it, measures width, then
  prints the suffix string `" Pokémon"` at `0x415F8F` (leading space = the only separator).
  The FR build drops that leading space → glued "MousePokémon" (the reported bug).

**FR fix = TWO separate class-3 patches in `make build-fr` (gba_translator), in this order:**

1. **Text** — `scripts/patch_pokedex_categories_fr.py` + `data/pokedex_categories_fr.json` (906
   EN→FR, official French: Mouse→Souris, Seed→Graine…, commit 423d88a). Writes the FR noun into
   the cell. **Does NOT touch the suffix or the print order** (the 5-day-old claim that it did
   the reorder was wrong — that work never landed; this ticket added it fresh).
2. **Order** — `scripts/patch_pokedex_category_order_fr.py` (commits 49391ed source + f43cded
   ROM regen, this session). Swaps print order → **"Pokémon Souris"** via 3 same-size Thumb
   edits in PrintMonInfo: 0x10588C `add r2,sp,#8`→`ldr r2,[pc,#0x30]` (print #1 = suffix);
   0x105896 →`ldr r1,[pc,#0x28]` (width advance measures suffix); 0x1058A4
   `ldr r2,[pc,#0x18]`→`add r2,sp,#8` (print #2 = category). Both ldr reuse the existing literal
   `0x1058C0`→`0x08415F8F`. Also flips suffix `0x415F8F` `" Pokémon"`→`"Pokémon "` (trailing
   space; accepts both source forms `00 ca…ff` and `ca…ff ff`).
   **This patch supersedes the old `patch_pokedex_category_fr.py`** (which only restored the
   leading space) — that script + its test were deleted. Proven by a unicorn before/after test
   (`test_patch_pokedex_category_order_fr.py`) that runs PrintMonInfo, stubs the print/width
   helpers, and asserts the call order flips: category-then-Pokémon → Pokémon-then-category.
