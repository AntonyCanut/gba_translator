---
name: unbound-de-pokedex-rewrap-width-overflow
description: DE build pokedex_rewrap blocker was width overflow (not free-space); tolerated in patch_pokedex_de.py; 130 French leftovers
metadata:
  node_type: memory
  type: project
  originSessionId: 02718b48-1fe2-4739-b419-440f4dd56a76
---

`make build-de` aborted at `patch_pokedex_de.py` with 169 `FAILED (display)`.
The ticket (slice of B-158) blamed free-space exhaustion — **wrong**.

**Why:** All 169 failures come from the `not pokedex.fits(rewrap(text))` check
(text too dense for the 232px reference line width), NOT `FreeSpaceAllocator`
(relocations succeeded: 61). `rewrap` always yields ≤3 lines, so these entries
never spill vertically — only a line exceeds 232px. DE also shipped an empty
`languages/de/data/pokedex_de_overrides.json` (`{}`) vs FR's 19.8KB curated set.

**Also:** ~130 of the 169 are **French leftover text** in the DE ROM (offsets
0xB2xxxx–0xB3xxxx in `de_translation_ready.json`) — untranslated species fall
back to French base. Tracked separately as follow-up B-160.

**How to apply:** For pokedex overflow, verify the failure source before
assuming free-space: run patch_pokedex_de.py directly and read the stats.
Fix (commit 65263c1): width overflow → tracked `overflow` warning + best-effort
3-line write, build only aborts on structural failure (bad pointer); no-space
relocation → benign in-place skip. Verified in isolation (exit 0, all 902 dex
entries ≤3 lines) — full build-de still gated on the sibling nature_names fix,
which was NOT yet merged onto `unbound`. See [[unbound-fr-build-lives-in-gba-translator]],
[[unbound-it-relocation-packing-fix]], [[unbound-pokedex-category-table]].
