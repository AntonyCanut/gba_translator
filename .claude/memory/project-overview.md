---
name: project-overview
description: Stack, entry points, folder map, and FR pipeline summary for gba_translator
metadata:
  type: project
---

**What it is**: GBA ROM translation toolkit for Pokemon Unbound (CFRU/BPRE01). Reverse-engineers English + Spanish ROMs, produces a French ROM translation.

**Why:** Owner Antony Canut is translating Pokemon Unbound from English to French. The Spanish community ROM serves as a reference for the reverse-engineering pipeline.

**How to apply:** Use `make build-fr` for any FR ROM work; use `make test` for quick validation. The build is fully automated — don't run individual scripts manually unless debugging.

## Key entry points

| Task | Command |
|---|---|
| Full EN→ES pipeline | `make pipeline` |
| Build FR ROM | `make build-fr` |
| Fast tests | `make test` |
| Audit FR quality | `python3 scripts/audit_translation_fr.py` |

## Core source modules

- `src/core/rom_reader.py` — `ROMReader`: load, read/write bytes + pointers
- `src/core/text_codec.py` — `POKEMON_TABLE` charmap encode/decode
- `src/core/text_reinserter.py` — inserts translated text, handles relocation
- `src/core/dialogue_linewrap.py` — 18-char-per-line dialogue wrap logic
- `src/core/fixed_tables.py` — ROM regions that must not be relocated
- `src/translators/19_build_translated_rom_generic.py` — THE build engine (main entry)
- `src/extractors/pointer_text_extractor.py` — pointer-based text extraction
- `src/analyzers/11_pointer_text_diff.py` — EN↔ES diff + offset map generation

## Translation data

- `combined_fr.txt` (2 MB) — master `<offset_hex> <FR_text>` translation file
- `output/translation/*_translation_ready.json` — structured JSON for build engine
- Trilingual CSV (`output/`) — EN/ES/FR export for translators

## Test layers

| Layer | Command | When |
|---|---|---|
| Unit (fast) | `make test` | Always |
| Python standard | `make test-python` | Pre-commit |
| Vitest (emulator-web) | `make test-vitest` | After TS changes |
| Playwright E2E | `make test-playwright` | After ROM build |

**Links:** [[domain-glossary]] [[fr-pipeline]] [[gotchas]] [[commands]]
