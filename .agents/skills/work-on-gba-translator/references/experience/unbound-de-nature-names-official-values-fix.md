---
name: unbound-de-nature-names-official-values-fix
description: Issue
metadata:
  node_type: memory
  type: project
  originSessionId: 8dfc520c-bbc4-42b0-b6c9-a15f9418aa00
---

`languages/de/patches/nature_names.py` (gba_translator) hardcodes the 25 official
German Pokémon nature names in a `TARGETS: dict[int, str]` keyed by original
EN ROM offset (patched by table index post-build, see
[[unbound-de-nature-names-table-driven-patch]]). A user (issue #41) reported
that 12 of the 25 were invented/wrong rather than the real localization, and
gave an authoritative EN→official-DE table in the issue body.

**Fix (commit b8bc50f, worktree of ticket 5641e31d):** corrected these 12 in
`TARGETS`: Lonely (Einsam→Solo), Docile (Sanftmut→Sanft), Impish
(Schelmisch→Pfiffig), Lax (Nachlässig→Lasch), Timid (Ängstlich→Scheu), Modest
(Bescheiden→Mäßig), Quiet (Still→Ruhig), Bashful (Schüchtern→Zaghaft), Calm
(Ruhig→Still), Sassy (Pfiffig→Forsch), Careful (Vorsichtig→Sacht), Quirky
(Wunderlich→Kauzig). Note Quiet/Calm and Impish/Sassy had been swapped with
each other. Updated `test_known_canonical_mappings` in
`tests/unit/de/test_patch_nature_names_de.py` to match (Lax/Timid/Quirky
assertions); other tests use their own local EN/DE lists so were unaffected.
9/9 unit tests pass.

**Why the discrepancy existed:** `languages/de/combined_de.txt` also carries
older/different hand-added nature words at the same 25 offsets (e.g. `Wirr`,
`Sachte`, `Skurril`) — but per
[[unbound-de-nature-names-table-driven-patch]] this file is NOT the source of
truth for nature names: `nature_names.py`'s post-build patch always
force-repoints both live pointer tables from `TARGETS`, ignoring whatever the
generic reinserter left from `combined_de.txt`. So `combined_de.txt` was left
untouched (it's dead weight for this specific string, already overwritten
downstream) — only `TARGETS` needed correcting.

**How to apply:** if a future report claims a DE nature name is wrong, edit
`TARGETS` in `nature_names.py` directly — do not chase `combined_de.txt` for
these 25 offsets.
