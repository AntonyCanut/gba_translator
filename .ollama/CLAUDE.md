# gba_translator — AI Memory (Ollama)

> Pokemon Unbound GBA ROM toolkit: reverse-engineers English + Spanish ROMs and
> produces a French ROM translation (CFRU / BPRE01 engine).

## Stack

- Python 3.11+ with pytest
- GNU Make (canonical entry point for all operations)
- Playwright + TypeScript (E2E via mGBA emulator)
- Vitest (TypeScript unit tests in `emulator-web/`)

## Folder map

```
src/core/           — shared library (ROMReader, text_codec, text_reinserter, dialogue_linewrap)
src/extractors/     — pointer-based text extraction
src/analyzers/      — binary diff, offset map generation
src/translators/    — ROM build engine (entry: 19_build_translated_rom_generic.py)
src/validators/     — byte-level ROM validation
src/cooker/         — mGBA emulator automation
scripts/            — standalone CLI tools (patch_font_fr, patch_time_format_fr, etc.)
tests/unit/         — fast tests, no ROM needed
tests/e2e/          — integration (needs ROM files)
tests/e2e-playwright/ — Playwright E2E (needs mGBA + ROM)
emulator-web/       — TypeScript GBA emulator browser harness
input/roms/         — source ROMs (READ ONLY)
output/roms/        — built ROMs: GenedRom-fr.gba, GenedRom-es.gba
combined_fr.txt     — master EN→FR translation file (2 MB)
```

## Commands

```bash
make install              # install all dependencies
make pipeline             # full EN→ES pipeline
make build-fr             # build French ROM
make test                 # fast unit tests (no ROM/emulator)
make test-python          # unit + integration tests
make test-playwright      # Playwright E2E tests
make sync-charmap-check   # verify Python↔TypeScript charmap sync
python3 scripts/audit_translation_fr.py   # FR quality audit
python3 scripts/spellcheck_combined_fr.py # spellcheck translation file
```

## Domain glossary

- **charmap**: `POKEMON_TABLE` in `src/core/text_codec.py` — maps Unicode chars to ROM bytes
- **POKEMON_TERMINATOR**: `0xFF` — string end marker
- **POKEMON_NEWLINE**: `0xFE` — line break
- **pointer**: 32-bit LE; file offset = `value − 0x08000000`
- **GBA_ROM_BASE**: `0x08000000`
- **combined_fr.txt**: `<hex_offset> <FR_text>` entries — last entry wins on duplicates
- **translation_ready.json**: structured JSON for build engine (`output/translation/`)
- **relocation**: moving a text block to free space when FR text is longer than original
- **fixed table**: ROM region that must not be relocated (species/move name tables)
- **LZ77**: GBA graphics compression format; must be repaired after text injection
- **mGBA**: GBA emulator used for E2E gameplay tests

## FR build pipeline (what `make build-fr` does)

1. `19_build_translated_rom_generic.py` — main injection
2. `patch_font_fr.py` — add FR glyph mappings
3. `patch_fixed_table_names.py` — patch hardcoded city/NPC names
4. `patch_time_format_fr.py` — Thumb code: DD/MM/YYYY, 24h, Dim..Sam
5. `apply_inline_overrides_fr.py` — inline text overrides
6. `repair_stable_lz77_blocks.py` — restore LZ77 images
7. `repair_localized_lz77_blocks.py` — restore localized LZ77
8. `repoint_stale_text_pointers.py` — fix stale pointers

## Non-obvious gotchas

1. **combined_fr.txt duplicates**: last entry wins — add at bottom, never use `csv.writer`
2. **Charmap sync**: after editing `text_codec.py`, run `make sync-charmap`
3. **Fixed tables**: `src/core/fixed_tables.py` — never relocate these addresses
4. **LZ77 repair**: always run after build; `make build-fr` does this automatically
5. **mGBA save**: NEVER save in-game during tests — corrupts `.sav` fixture files
6. **Intro font**: `ê`, `ç`, `ù` glyphs missing from fullscreen intro font
7. **Test markers**: exclude `emulator` and `rom` in CI (no ROM files available)
8. **Positional placeholders**: preserve `{0}`, `{1}` order in FR strings
