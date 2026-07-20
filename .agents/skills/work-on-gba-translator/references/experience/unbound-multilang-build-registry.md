---
name: unbound-multilang-build-registry
description: Multi-language (FR/IT/DE) build structure in gba_translator and the FR_TRANSLATION glob trap
metadata:
  node_type: memory
  type: project
  originSessionId: c73c9cd8-5df3-4d71-bcb8-ca816ca4e91a
---

gba_translator now builds FR/IT/DE from one registry: `languages/<code>/lang.yaml`
(loaded by `src/i18n`, `load_registry()`), translations in
`languages/<code>/combined_<code>.txt` (FR keeps `combined_fr.txt` at root).

- **FR = `build: dedicated`** — the byte-perfect `make build-fr` recipe, UNTOUCHED. Verified reproducible hash `9974191aa2d0...`. Never reroute FR through the generic driver.
- **IT/DE = `build: generic`** — `scripts/build_language.py <code>` (combined → trilingual CSV via the language-agnostic `apply_combined_fr.py` → `<code>_translation_ready.json` → generic builder → font/inline). `make build-it` / `build-de` / `build-all` / `release-all` (→ `scripts/package_release.py`, output/release/).

**TRAP (caught by byte-verify):** `build-fr`'s `FR_TRANSLATION` selected the newest `*_translation_ready.json` by mtime. The generic driver writes `it_/de_translation_ready.json` into the same dir → `build-fr` injected German/Italian → FR ROM hash changed. Fix: glob narrowed to `[0-9]*_translation_ready.json` (date-prefixed = FR only). Always re-run `make build-fr` and diff the hash after any multi-lang change.

Charmap gap: `à è é ì í î ò ó ù ú ç ß` encode; `ä ö ü` do NOT — DE transliterates umlauts (ae/oe/ue/ss) and disables its `font` step until follow-up F-51 adds a DE charmap+font. IT reuses the FR font. Build artifacts (it/de ROMs, release/, lang jsons/csvs) are gitignored. See `docs/21_MULTILANGUE.md`. Related: [[unbound-fr-build-lives-in-gba-translator]].
