# ROM Sources and Baseline

The public CI and release workflows use no ROM input. Their only release
inputs are the four tracked BPS files and metadata under `patches/`.

For ordinary local tests, the developer supplies one legally obtained,
compatible English Unbound ROM:

- input/roms/englishrom.gba — source of the tracked FR/IT/DE/Indie BPS.

`make materialize-test-roms` verifies that local source against the manifest,
applies every patch, verifies each target and writes only ignored files under
`output/roms/`.

The historical source builder still uses three private ROMs when a maintainer
intentionally regenerates the tracked patch bundle. They are ignored by Git:
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

Verify maintainer inputs before a source rebuild:
- python3 scripts/verify_roms.py --baseline docs/roms_baseline.json

GitHub Actions never downloads these inputs. Python ROM and Playwright suites
are local because applying a BPS necessarily requires the source ROM bytes.
The public CI runs ROM-less pytest/Vitest checks plus
`scripts/verify_patch_bundle.py`.

Release packaging compares each built target with its declared source and
produces only `pokemon_unbound_<lang>.bps`. All distributed patches are
calculés depuis `englishrom.gba`, y compris FR : `patchedfrenchrom.gba` reste
strictement une base de compilation interne. Le candidat est écrit sous
`output/release/`, puis `scripts/promote_patch_bundle.py` copie seulement un
bundle complet et vérifié vers `patches/`. If the ROMs ever change, create a
separate compatibility migration; never silently regenerate the baseline for
a different source lineage.
