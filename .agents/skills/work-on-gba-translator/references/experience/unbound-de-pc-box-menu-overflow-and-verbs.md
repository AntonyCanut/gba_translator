---
name: unbound-de-pc-box-menu-overflow-and-verbs
description: "DE PC Box main menu \"Move Items\" desc overflowed 2-line box (#38); shortened verbs to match official style"
metadata:
  node_type: memory
  type: project
  originSessionId: 0f394bca-399b-43d9-b9d4-baf353177471
---

Fixed GitHub issue #38 in `gba_translator/languages/de/combined_de.txt` (offsets 0x41856C-0x418642, PC Box main menu: labels + help-text descriptions, same table FR fixed in [[unbound-pc-selection-menu-fix-and-dead-patch-script]]/test_pc_item_from_menu_descriptions_fr.py).

**Bug**: "Verschiebe getragene Items eines Pokémon aus einer Box oder dem Team." — 2nd line ≈207px, past the box's ~192px (`DEFAULT_MAX_LINE_WIDTH`) edge, clipping "Team." behind the scroll arrow. Measured with `src/core/dialogue_linewrap.line_widths()`.

**Fix**: adopted the user's requested shorter verbs (verschieben→bewegen, entnehmen→nehmen, einlagern→ablegen — these already match "Item ablegen"/"Item entnehmen" used elsewhere in the ROM for the Item Depot, so it's consistent, not just shorter) across all 4 labels + 4 descriptions, and reworded the Move Items description ("...aus Box oder dem Team." dropping "einer") to fit 2 lines again — swapping just the verb wasn't enough, the 2nd line (which doesn't contain the verb) was independently too long and needed its own trim.

**Verification gotcha**: reading the fixed offsets directly in the built ROM after `make build-de` showed 5 of 8 entries still in English, even though `de_translation_ready.json` had the correct German text. This table is **pointer-relocated**, not written in-place — the original fixed offsets hold stale/reused English bytes post-build. Confirmed correct by resolving the live pointer (find the 4-byte LE pointer to `0x08000000+offset` in `input/roms/englishrom.gba`, then read that same pointer slot's value in the built ROM and decode there). Same pattern as [[unbound-trace-live-pointer-not-original-offset]].

Added `tests/test_pc_menu_descriptions_de.py` (build-independent, reads combined_de.txt directly) mirroring the FR guard for the same box.
