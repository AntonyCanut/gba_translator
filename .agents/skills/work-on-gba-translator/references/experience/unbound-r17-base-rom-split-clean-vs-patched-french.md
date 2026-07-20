---
name: unbound-r17-base-rom-split-clean-vs-patched-french
description: "R-17: englishrom.gba split into a clean base (DE/IT/other langs) + patchedfrenchrom.gba (build-fr only); how the swap was validated"
metadata:
  node_type: memory
  type: project
  originSessionId: 0e56621b-c27d-4d9b-bba0-597309a0b585
---

Ticket R-17 "Base Rom" asked to stop using the French-contaminated
`englishrom.gba` (see [[unbound-englishrom-french-contaminated-base]]) as the
shared base for every language. No ROM was attached to the ticket — "la rom
suivante" (the following ROM) referred to nothing in the MCP attachments. The
only viable candidate found on disk was
`~/Downloads/Pokemon Unbound v2.1.1/Pokemon Unbound (v2.1.1.1).gba`: the zip
it came from was downloaded the same calendar day as the ticket (confirmed via
`stat -f "%Sm"`), and it's the only other Unbound-named GBA ROM anywhere on the
machine. When a ticket references an unattached "following file/ROM", check
recent Downloads timestamps before asking — a same-day download is decisive
circumstantial proof, not just a guess.

Mechanics: renamed the old (French-patched) `input/roms/englishrom.gba` to
`input/roms/patchedfrenchrom.gba`, installed the clean ROM as the new
`englishrom.gba`. Both files are git-TRACKED in gba_translator (no .gitignore
for `*.gba` there, unlike Test/Unbound) — the rename/swap is a normal
committable diff, no untracked-wipe risk.

Makefile: added `FRENCH_ROM`/`FRENCH_EXTRACT` vars, redirected `build-fr` and
`prepare-fr` to them; left `extract-en`/`build-es`/`verify-roms` and
`scripts/build_language.py` (IT/DE/Indie) pointed at `ENGLISH_ROM` — that
script hardcodes the same `input/roms/englishrom.gba` path independently of
the Makefile, so it picked up the clean ROM automatically with zero code
change. Two FR sub-steps had hidden `--english-texts` argparse defaults
pointing at the now-defunct `englishrom_texts.json` (`repoint_stale_text_pointers.py`
crashed outright; `apply_inline_overrides_fr.py` degraded silently to an empty
placeholder map) — both needed an explicit `--english-texts $(FRENCH_EXTRACT)`
override added to the Makefile recipe.

Validation performed: `make build-fr` end-to-end (all 3 in-build FR guard
pytest files green), `make build-it`/`make build-de` complete with 0 errors
against the new clean base, full fast pytest tier (1359 passed) and `-m rom`
tier (150 passed) green pre- and post-rebase. NOT verified: whether DE/IT
patch scripts whose offsets were reverse-engineered against the old
contaminated ROM still hit live tables on the new clean ROM (e.g. move_names.py
writes to 0x1B2980, which is raw 0xFF/unused in the clean ROM) — filed as
follow-up B-189, out of scope for the rename itself.
