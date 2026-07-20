---
name: unbound-dedicated-patch-script-reintroduces-phantom-offset
description: "gba_translator dedicated post-build patch scripts (hardcoded offset + bytes) can silently reintroduce a bug even after combined_fr.txt is fixed — the script itself must also be checked/removed (issue #118, 'QQuoi ?')"
metadata:
  node_type: memory
  type: project
  originSessionId: e40d122f-b0bf-4e66-b9a8-9290be12e23f
---

Issue #118: evolution message showed "QQuoi ?" (duplicate leading letter) instead
of "Quoi ?". Root cause was NOT a bad translation in `combined_fr.txt` — the real
entry at `0x3FE672` was correct and untouched for 6 months. A prior "fix" commit
(5f5b2e0c) added a **second**, off-by-one entry at `0x3fe673` (one byte into the
same string — English there reads "hat?..." not "What?...") via two independent
mechanisms: (1) a `combined_fr.txt` line picked up by the no-pointer in-place
fallback, and (2) a **dedicated post-build patch script**
(`scripts/patch_evolution_message_fr.py`, wired unconditionally into `make
build-fr`) that hardcoded the same wrong offset and bytes.

**Why this was hard to find:** removing the `combined_fr.txt` phantom line alone
did NOT fix the ROM — the dedicated script re-corrupted it on every rebuild
regardless of `combined_fr.txt` content. Root-caused by tracing the actual
`SmartReinserter.reinsert_text` write for the offset (byte-correct in isolation),
then diffing against the final built ROM to find a SECOND write landing 1 byte
later.

**How to apply:** when a single-string FR/DE/IT bug (especially one with a
duplicated/off-by-one character) persists after fixing the obvious
`combined_fr.txt` entry, grep the Makefile's `build-fr`/`build-it`/`build-de`
target for a **dedicated patch script** touching a nearby or identical offset
(`grep -rn "0x<offset ± few bytes>" scripts/ languages/*/patches/`). These
scripts run unconditionally and silently override whatever the generic pipeline
already got right. See also [[unbound-phantom-tail-overlap-verb-buffer-corruption]]
and [[unbound-fr-build-lives-in-gba-translator]].
