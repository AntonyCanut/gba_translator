---
name: unbound-de-species-and-move-names-fixed-table-gap
description: "gba_translator DE build never wrote gSpeciesNames (0x166A997, 11-byte stride, 1293 entries) or the move-name table — combined_de.txt already had 937/498 translations authored, just never wired (issue #81)"
metadata:
  node_type: memory
  type: project
  originSessionId: 9832ad01-2122-4426-9a49-ae5ec99354fb
---

Issue #81 ("DE 2.1.51 Pokemon Namen und Attacken Namen sind alle auf
Englisch"): both the species-name table (`gSpeciesNames`-equivalent, fixed
11-byte stride, 1293 entries, base offset **0x166A997** = "Bulbasaur",
National Dex #1, last real entry index 1292 = "Urshifu") and the move-name
table (see [[unbound-move-names-real-table-vs-legacy-offset]]) are
class-2 fixed tables with no per-entry pointer, invisible to the generic
translation pipeline. `languages/de/combined_de.txt` already had the data —
937 species names + 498 move names authored at the correct offsets — but
`languages/de/lang.yaml` never wired a patch step to write them, so the
built ROM shipped English (this is the sibling gap to the move-names DE bug
noted as "still open" in the move-names memory above).

Fix (landed, `languages/fr/patches/species_names.py` new language-agnostic
core mirroring `move_names.py`, + `languages/de/patches/{move_names,
species_names}.py` thin delegate wrappers, + both steps added to
`languages/de/lang.yaml` patches: list near `ability_names`). Verified by
decoding a fresh `GenedRom-de.gba` copy post-patch: 0x166A997 → "Bisasam"
(was "Bulbasaur"), 937/1293 species + 498/894 move names patched; the rest
are either not yet authored in combined_de.txt or overflow the fixed cell
width and stay English with a logged warning (translation-content gap, not
a wiring bug).

**Trap avoided**: `languages/en/combined_en.txt` records **stale French**
names at this exact offset range (e.g. "Bulbizarre" at 0x166A997) — a
leftover from before the R-17 clean-base split
([[unbound-r17-base-rom-split-clean-vs-patched-french]]). The sibling
`ability_names.py` pattern validates each cell against `combined_en.txt`
before overwriting; reusing that pattern here would have silently rejected
every write (current ROM cell = "Bulbasaur", stale EN record = "Bulbizarre"
→ mismatch → skip). Used the simpler `move_names.py`-style direct
idempotent overwrite (no combined_en validation) instead — safe here
because, unlike the FR-patched-base move-name table, `gSpeciesNames` was
confirmed identical-offset in both the pristine `englishrom.gba` and the
DE-built ROM (never relocated by any pipeline in this repo).

**IT has the same species_names gap** (move_names was already fixed for IT
earlier) — filed as follow-up ticket B-273, not fixed in #81 (DE-only scope).

**Process note**: lost a full round of edits + new files by editing directly
in the shared `/Users/akc/Projects/Test/gba_translator` checkout instead of
calling `orchestration_prepare_worktree` first — the engine resets
uncommitted changes there. Redid everything inside the proper worktree. See
[[singularity-worktree-commit-early]] and [[singularity-build-resets-worktree]] —
always prepare_worktree BEFORE the first Write/Edit in a project, not just
before commits.
