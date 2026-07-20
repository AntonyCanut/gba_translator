---
name: unbound-pc-selection-menu-fix-and-dead-patch-script
description: PC-selection menu translation fix (issue
metadata:
  node_type: memory
  type: project
  originSessionId: 1977a932-99ea-468b-a153-6a920e640b09
---

Fixed 3 offsets in `gba_translator/languages/fr/combined_fr.txt` (GitHub issue #18):
- 0x417BB6 — the player's-own-PC menu entry ("{PLAYER}'s PC") had **no entry at all** in combined_fr.txt, so it rendered as raw untranslated English. Added `PC de {PLAYER}`.
- 0x417BD3 — `PC Prof. Log` → `PC du Prof. Log`.
- 0x1A508A — `Quel PC doit être utilisé ?` → `Accéder à quel PC ?`.

These sit in a compact back-to-back string table (badge names, PC menu, Eevee-line names) that looks like a fixed non-relocatable table by byte-adjacency alone, but is actually **pointer-reachable and relocatable** by the generic builder (`--allow-relocate`) — proven by pre-existing entries already longer than their English budget (e.g. "BADGE MARAIS" 12 chars vs "MARSHBADGE" 10-byte budget). Don't assume byte-adjacency means non-relocatable; check via `_pointer_count`/pointer search before worrying about budget overflow. See [[unbound-nopointer-inplace-budget]] for the *actual* non-relocatable case (budget = en_len, silently skips to English if too long).

To verify a relocated string post-build: find the pointer-table slot in the **source** ROM (`input/roms/patchedfrenchrom.gba`, pre-build) that targets `0x08000000 + original_offset`, then read the pointer *value* at that same file position from the **built** ROM (`output/roms/GenedRom-fr.gba`) — the original fixed offset in the built ROM holds stale/reused bytes once relocated.

Discovered along the way: `languages/fr/patches/pc_messages.py` exists (handles "Someone's PC" transfer/box-full messages at 0x1A5CF1/0x1A5D6E) but is **never invoked** by `make build-fr` in the Makefile — DE has the equivalent wired in via `lang.yaml`'s `pc_messages` step, FR does not. Not fixed as part of this ticket (out of scope, no bug report against it yet) — worth checking if those two messages are still untranslated in the shipped FR ROM.

Build chain used: `make prepare-fr` (regenerates dated `translation_ready.json` from combined_fr.txt, bypasses CSV) → `make build-fr` → `make test-rom`. Added `tests/e2e/fr/test_pc_selection_menu.py` to lock the fix in via live-pointer resolution.
