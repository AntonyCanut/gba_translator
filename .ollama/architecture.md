# Architecture — gba_translator (Ollama)

## What this project does

Translates the Pokémon Unbound GBA ROM from English to French.
Patches the proprietary Gen III (CFRU/BPRE01) text encoding, pointer tables,
and binary regions without modifying the game engine.

## Language layers

| Layer | Runtime | Location |
|---|---|---|
| Translation pipeline | Python 3.11+ | `src/`, `scripts/` |
| Web emulator (mGBA-WASM) | TypeScript / Node 20 | `emulator-web/` |
| E2E test runner | Playwright | `tests/e2e-playwright/` |

## Python source tree

```
src/
  core/          Shared library (ROMReader, TextCodec, PaddingDetector, TextReinserter)
  text/          CFRU charmap data
  extractors/    Text extraction from ROM
  translators/   FR injection pipeline
  cooker/        mGBA automation
  analyzers/     ROM structure analysis
  utils/         Shared helpers
  validators/    Injection validators
```

## Critical domain facts

- Text encoding is CFRU charmap — **not ASCII or UTF-8**. See `src/text/charmap_data.py`.
- Every string ends with byte `0xFF`.
- Control codes `FC`, `FD`, `F8`, `F9`, `F7` are 2–3 bytes wide.
- Pointers are 32-bit little-endian with base address `0x08000000`.
- Main text lives at `0x1F00000–0x1F80000`.
- `FA`/`FB` bytes are **not** translation tokens.
- `combined_fr.txt` duplicate offsets: the **last** entry wins.

## Architecture rules

1. All shared logic → `src/core/`. Never duplicate code across scripts.
2. `input/` (source ROMs) is read-only. All generated files go to `output/`.
3. Patch ROMs only after writing `*.gba.bak`.
4. No Python files at project root.
5. Documentation files in `docs/` must be numbered: `NN_NAME.md`.
6. Git commits: `type(scope): description`. No Co-Authored-By trailers.

## emulator-web

Express 5 HTTP server + `ws` WebSocket bridge.
Serves mGBA compiled to WASM in Chromium for Playwright E2E tests.
Port: `process.env.EMULATOR_PORT` (default 3000).
ROM path: `process.env.ROM_PATH` (default `output/roms/GenedRom-fr.gba`).
