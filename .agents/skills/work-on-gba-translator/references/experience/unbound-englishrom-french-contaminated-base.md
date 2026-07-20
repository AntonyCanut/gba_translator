---
name: unbound-englishrom-french-contaminated-base
description: "RESOLVED by R-17: englishrom.gba is now a clean vanilla ROM; the old French-contaminated ROM was renamed patchedfrenchrom.gba and is used only by build-fr"
metadata:
  node_type: memory
  type: project
  originSessionId: c375d65c-4c3a-4034-86bc-63141bb1498b
---

**Historical bug, fixed by ticket R-17 "Base Rom" (2026-07-06).** `input/roms/englishrom.gba`
(in gba_translator) used to NOT be a pristine English CFRU compile — it shipped
official **French** baked into every major content table: move names
(0x1B2980), move descriptions (0x0480000 legacy + free-space pool
0x0B2*–0x0C2*, 0xA37*), item names (0x0876074), item descriptions (0x03D0000,
0x0EB0000), Pokédex flavour (0x0440000, 0x0950000, 0x1650000), species names
(0x166A981). Because the leak was in the shared base, IT/DE builds silently
shipped French wherever they lacked a dedicated patch.

**Fix**: the old French-patched ROM was renamed to `input/roms/patchedfrenchrom.gba`
and is now the ONLY source for `make build-fr` (Makefile `FRENCH_ROM`/
`FRENCH_EXTRACT` vars). A genuinely clean vanilla Unbound ROM (sourced from
`~/Downloads/Pokemon Unbound v2.1.1/Pokemon Unbound (v2.1.1.1).gba`, the only
non-project Unbound ROM found on disk, downloaded the same day as the ticket)
was installed as the new `input/roms/englishrom.gba` — the base for
`build-es`/`build-it`/`build-de`/`build-indie`/`build-lang` and all shared
extraction/diff tooling (`scripts/build_language.py`'s `ENGLISH_ROM` constant
needed no change since the filename didn't move, only its content).

`docs/roms_baseline.json` now guards all three ROMs. Guard test
`tests/unit/test_audit_english_rom_french_leak.py` was flipped: contamination
is now asserted on `patchedfrenchrom.gba`, and a new test asserts its absence
from `englishrom.gba`. `tests/test_patch_move_descriptions.py`'s
`SOURCE_ROM` (FR-only, byte-exact test) was repointed to `patchedfrenchrom.gba`
too. Two Makefile FR sub-steps (`repoint_stale_text_pointers.py`,
`apply_inline_overrides_fr.py`) had hidden `--english-texts` defaults pointing
at the now-decommissioned `englishrom_texts.json` — had to pass
`--english-texts $(FRENCH_EXTRACT)` explicitly or build-fr silently degraded
(one crashed outright, the other silently fell back to an empty placeholder
map). `make build-fr` reproduces byte-for-byte (all 3 in-build FR guard tests
pass); `make build-it`/`make build-de` complete successfully against the new
clean base too.

**Not yet verified**: whether DE/IT patch scripts whose target offsets were
reverse-engineered against the OLD (French-patched) ROM still hit the correct
*live* table on the new clean ROM — e.g. `move_names.py` writes into
0x1B2980, which is 0xFF/unused in the raw clean ROM before any build step.
The generic build for IT/DE completes with zero errors and 0 collisions, but
that doesn't prove those cells are actually pointed-to in-game. Tracked as a
follow-up: B-189.

Related: [[unbound-move-names-real-table-vs-legacy-offset]],
[[unbound-fr-build-lives-in-gba-translator]], [[combined-fr-duplicate-offsets-last-wins]].
