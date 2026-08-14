# ROM Sources and Baseline

This project uses three private ROMs as build inputs. They are ignored by Git,
must be obtained legally, and are never uploaded as CI or release artifacts:
- input/roms/englishrom.gba — clean vanilla Unbound base. Used by build-es, the
  generic multi-language driver (build-it/build-de/build-indie/build-lang) and
  all shared extraction/diff tooling.
- input/roms/patchedfrenchrom.gba — the same ROM lineage but with official
  French already baked into it (move/item/Pokédex tables etc. — see
  docs/english-rom-french-leak-audit.md for the historical contamination
  audit). build-fr is the ONLY consumer: combined_fr.txt and every dedicated
  languages/fr/patches/*.py script were tuned against this exact byte layout,
  so FR must never be rebuilt from the clean englishrom.gba.
- input/roms/spanishrom.gba — community Spanish translation, used as a
  reference/validation ROM (build-es, pointer-proof checks).

Baseline metadata (size + sha256):
- docs/roms_baseline.json

Baseline metrics (text counts and diffs):
- docs/baseline_report.json

Verify inputs before any build:
- python3 scripts/verify_roms.py --baseline docs/roms_baseline.json

GitHub Actions downloads the same inputs from `UNBOUND_ENGLISH_ROM_URL`,
`UNBOUND_PATCHED_FRENCH_ROM_URL`, and `UNBOUND_SPANISH_ROM_URL`. These secrets
must be private URLs. The workflow verifies all three inputs before building.

Release packaging compares each built target with its declared source and
publishes only `pokemon_unbound_<lang>.bps`. Tous les patchs distribués sont
calculés depuis `englishrom.gba`, y compris FR : `patchedfrenchrom.gba` reste
strictement une base de compilation interne. If the ROMs ever change, create a
separate compatibility migration; never silently regenerate the baseline for
a different source lineage.
