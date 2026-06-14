# gba_translator — AI Memory (Claude)

> Pokemon Unbound GBA ROM toolkit: reverse-engineers English + Spanish ROMs and
> produces a French ROM translation (CFRU / BPRE01 game engine).

## Stack

| Layer | Tech |
|---|---|
| Language | Python 3.11+ |
| Tests (unit/integration) | pytest |
| Tests (E2E / browser) | Playwright (TypeScript) + mGBA WebSocket |
| Tests (emulator-web) | Vitest |
| ROM emulation | mGBA (headless + WebSocket) |
| Build automation | GNU Make |
| External deps | pyyaml ≥ 6.0, playwright, vitest |

## Folder Map

```
gba_translator/
├── CLAUDE.md               ← this file (Claude AI memory)
├── AGENTS.md               ← Codex AI memory
├── Makefile                ← canonical entry point for all operations
├── pyproject.toml          ← Python project config + pytest markers
├── combined_fr.txt         ← master EN→FR translation file (2 MB, ~9 k entries)
│
├── src/
│   ├── core/               ← shared library (import from here everywhere)
│   │   ├── rom_reader.py           — ROMReader class (load, read/write bytes/pointers)
│   │   ├── text_codec.py           — encode/decode text using POKEMON_TABLE charmap
│   │   ├── text_converter.py       — higher-level text conversion helpers
│   │   ├── text_reinserter.py      — inserts translated text into ROM, handles relocation
│   │   ├── text_validator.py       — validates reinsertion (ranges, overflows)
│   │   ├── padding_detector.py     — detects free bytes after a text block
│   │   ├── enhanced_padding_detector.py — advanced padding analysis
│   │   ├── dialogue_linewrap.py    — line-wrap logic for dialogue boxes (18 chars/line)
│   │   ├── fallback_translator.py  — token-by-token fallback when full text doesn't fit
│   │   └── fixed_tables.py         — list of ROM regions that must not be relocated
│   │
│   ├── extractors/
│   │   └── pointer_text_extractor.py   — scans ROM pointers → extracts all text blocks
│   │
│   ├── analyzers/
│   │   ├── 11_pointer_text_diff.py     — diffs EN vs ES extracts → offset map
│   │   └── (numbered legacy scripts)
│   │
│   ├── translators/
│   │   ├── 19_build_translated_rom_generic.py  — THE build engine (57 KB, main entry point)
│   │   ├── 28_export_trilingual_csv.py          — exports EN/ES/FR trilingual CSV
│   │   └── (numbered legacy variants)
│   │
│   ├── validators/
│   │   └── text_range_validator.py     — byte-for-byte validation vs reference ROM
│   │
│   ├── commands/
│   │   └── build_rom.py                — CLI wrapper for build_translated_rom_generic
│   │
│   ├── text/
│   │   └── charmap_data.py             — raw CFRU charmap table data
│   │
│   ├── utils/                          — misc helpers
│   └── cooker/
│       ├── emulator.py                 — mGBA process launcher + WebSocket client
│       └── checkpoint.py               — saves/restores mGBA savestates for scenario tests
│
├── scripts/                ← standalone CLI tools (not imported as modules)
│   ├── apply_combined_fr.py            — apply combined_fr.txt to a built FR ROM
│   ├── apply_inline_overrides_fr.py    — inject inline text overrides
│   ├── audit_translation_fr.py         — quality audit of FR translation
│   ├── export_dynamic_trilingual_csv.py — dynamic CSV export
│   ├── patch_font_fr.py                — patch ROM font table for FR glyphs
│   ├── patch_fixed_table_names.py      — patch known fixed-table strings (places, NPCs)
│   ├── patch_time_format_fr.py         — patch date/time code to FR format (DD/MM/YYYY, 24h)
│   ├── repoint_stale_text_pointers.py  — fix pointers that still point to old addresses
│   ├── repair_localized_lz77_blocks.py — restore LZ77-compressed images with FR text
│   ├── repair_stable_lz77_blocks.py    — restore LZ77 blocks that regress after injection
│   ├── run_playwright_tests.py         — orchestrates Playwright runs with mGBA
│   ├── spellcheck_combined_fr.py       — spellcheck combined_fr.txt entries
│   ├── sync_charmap.py                 — sync charmap Python→TypeScript
│   └── verify_roms.py                  — verify ROM checksums against docs/roms_baseline.json
│
├── tests/
│   ├── unit/               ← fast, no ROM needed
│   ├── e2e/                ← Python integration tests (need ROM files)
│   ├── e2e-playwright/     ← Playwright specs (need mGBA + ROM)
│   ├── benchmarks/         ← performance benchmarks (slow)
│   └── stress/             ← stress tests (very slow)
│
├── emulator-web/           ← TypeScript browser harness + Vitest unit tests
│   └── src/                — GBA emulator WebAssembly wrapper
│
├── input/
│   └── roms/               ← source ROMs (READ-ONLY, never modify)
│       ├── englishrom.gba  — English source (BPRE01)
│       └── spanishrom.gba  — Spanish community translation (reference)
│
└── output/
    ├── roms/               — built ROMs: GenedRom-es.gba, GenedRom-fr.gba
    ├── extracted/          — pointer-extracted JSON text corpora
    ├── differences/        — EN↔ES diff + offset map JSON
    ├── translation/        — *_translation_ready.json (inputs to build-fr)
    └── reports/            — validation + quality reports
```

## Canonical Commands

```bash
# Install everything
make install                    # pip install -e ".[dev]" + npm install

# Full ES pipeline (extract → diff → build → validate)
make pipeline

# Build French ROM
make build-fr                   # uses latest output/translation/*_translation_ready.json

# Tests — fast (unit only, no ROM/emulator)
make test                       # alias: test-python-fast
python3 -m pytest tests/ -x --ignore=tests/benchmarks --ignore=tests/e2e \
    -m "not slow and not stress and not emulator and not rom"

# Tests — standard (unit + integration, no emulator)
make test-python

# Tests — Vitest (emulator-web TypeScript)
make test-vitest

# Tests — Playwright E2E (needs mGBA + ROM)
make test-playwright

# Validate charmap sync (Python ↔ TypeScript)
make sync-charmap-check

# Spellcheck combined_fr.txt
python3 scripts/spellcheck_combined_fr.py

# Quality audit
python3 scripts/audit_translation_fr.py

# List open tickets
make tickets
```

## FR Build Pipeline (step by step)

`make build-fr` runs these in order:
1. `19_build_translated_rom_generic.py` — copy EN ROM, inject translations from JSON
2. `patch_font_fr.py` — add FR glyphs to font table
3. `patch_fixed_table_names.py` — patch hardcoded location/NPC names
4. `patch_time_format_fr.py` — patch Thumb code for DD/MM/YYYY, 24h clock
5. `apply_inline_overrides_fr.py` — inject inline (non-pointer) text overrides
6. `repair_stable_lz77_blocks.py` — restore LZ77-compressed images
7. `repair_localized_lz77_blocks.py` — restore localized LZ77 blocks
8. `repoint_stale_text_pointers.py` — fix any stale pointers after relocation

## Domain Glossary

| Term | Meaning |
|---|---|
| **GBA** | Game Boy Advance |
| **BPRE01** | Pokemon FireRed ROM identifier |
| **CFRU** | Custom FR engine base used by Pokemon Unbound |
| **charmap** | Table mapping Unicode chars to ROM byte values |
| **POKEMON_TERMINATOR** | `0xFF` — marks end of a string in ROM |
| **POKEMON_NEWLINE** | `0xFE` — line break within a text block |
| **control code** | Multi-byte sequences: `0xFC`, `0xFD`, `0xF8`, `0xF9`, `0xF7` |
| **pointer** | 32-bit LE address in ROM; physical = `value − 0x08000000` |
| **offset** | Byte position in the ROM file |
| **GBA_ROM_BASE** | `0x08000000` — ROM address space base |
| **combined_fr.txt** | Master translation file: `<offset_hex> <FR_text>` lines |
| **translation_ready.json** | Structured JSON consumed by the build engine |
| **offset map** | EN→ES pointer→offset mapping (JSON) |
| **relocation** | Moving a text block to free space when FR text is longer |
| **repoint** | Updating a pointer to its new target after relocation |
| **fixed table** | ROM region whose address must not change (species/move names, etc.) |
| **LZ77** | Compression used for ROM graphics; patches must preserve it |
| **IPS** | ROM patch format (records: offset + bytes) |
| **trilingual CSV** | EN/ES/FR text export for translators |
| **mGBA** | GBA emulator used for Playwright/cooker tests |
| **savestate** | mGBA snapshot — used as fixtures in Playwright tests |

## Key Technical Facts

### Text Encoding
- Proprietary charmap in `src/core/text_codec.py` (`POKEMON_TABLE` + accented extensions)
- Terminator: `0xFF` | Newline: `0xFE` | Space: `0x00`
- FR glyphs: `é è ê ë à â ç ù û ü î ï ô œ` and uppercase variants — all mapped
- Control codes 2–3 bytes: `FC nn`, `FD nn`, `F8 nn`, `F9 nn`, `F7 nn nn`
- `{COLOR}X` → `FC 01 NN`; `{LV}` → `0x34`

### combined_fr.txt
- ~957 duplicate offsets in the file; **last entry wins**
- Small lowercase-only block near end of file is the **live** block — edits go there
- Insertion is surgical (never use `csv.writer` — it would reformat 30k lines)

### Trilingual CSV (CRLF hazard)
- The CSV file uses CRLF line endings **and** LF inside field values
- Use surgical byte-level insertion; never re-write the whole file

### Pointers
- All text pointers: 32-bit little-endian at `pointer_value − 0x08000000` = file offset
- Valid pointer range: `0x08000000`–`0x0BFFFFFF`

### mGBA Probe Quirks
- `Aaaaaaa`/`Fffffff` in probe output = naming-screen button mash, not real text
- Sudden disconnects on bridge routes = flakiness, not a crash
- **NEVER save in-game** during probe sessions — overwrites `.sav` fixtures → Playwright goldens break
- Use short sessions + savestates

### Date/Time Patches
- `patch_time_format_fr.py` patches Thumb assembly code **post-build**
- Implements DD/MM/YYYY, 24h clock, Dim..Sam, "Jamais" strings

### Gendered buffers
- Son/daughter text: delivered via opcode 85 (son=fils, daughter=fille)
- Avoid "mon {fille}" — use "mon enfant" instead; use il/elle for pronouns

## Non-Obvious Gotchas

1. **combined_fr.txt duplicates** — last entry wins; always add to the lowercase block at the bottom, never to the top.
2. **charmap sync** — Python `text_codec.py` and TypeScript must stay in sync; run `make sync-charmap-check` after any charmap edit.
3. **test markers matter** — `emulator`, `rom`, `slow`, `stress` gates skip in CI. Fast suite: `-m "not slow and not stress and not emulator and not rom"`.
4. **fixed tables** — `src/core/fixed_tables.py` lists regions whose addresses must never change. Passing `--allow-relocate` without this guard corrupts species/move name lookups.
5. **LZ77 regression** — after build-fr, run `repair_stable_lz77_blocks.py`; skipping it causes graphical corruption.
6. **Stale pointers** — text relocation leaves old pointers pointing at garbage; `repoint_stale_text_pointers.py` is mandatory at end of build-fr.
7. **intro font** — glyphs `ê`, `ç`, `ù` are absent from the fullscreen intro font; avoid them in intro text.
8. **mGBA never save** — saving in-game during tests corrupts the `.sav` fixture files.
9. **positional placeholders** — the build engine uses positional token replacement; never swap `{0}` and `{1}` in FR strings.
10. **FA/FB opcodes** — these are outside the token file; do not add them to combined_fr.txt.
