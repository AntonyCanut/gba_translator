# Architecture — gba_translator (Codex)

## Language layers

| Layer | Runtime | Root |
|---|---|---|
| Translation pipeline | Python 3.11+ | `src/`, `scripts/` |
| Web emulator server | TypeScript / Node 20 | `emulator-web/` |
| E2E tests | Playwright (Node) | `tests/e2e-playwright/` |
| Unit tests (TS) | Vitest | `emulator-web/tests/` |
| Unit/integration tests (Py) | pytest | `tests/` |

## Python src layout

```
src/
  core/          ROMReader, TextCodec, PaddingDetector, TextReinserter, FallbackTranslator
  text/          charmap_data.py (CFRU charmap, not ASCII)
  extractors/    String finder, dump formats
  translators/   CSV/JSON pipeline, space manager
  cooker/        mGBA automation (checkpoint.py, emulator.py)
  analyzers/     Structure analysis
  commands/      CLI wrappers
  utils/         Shared helpers
  validators/    Pre/post-injection validators
```

## Domain invariants

- Terminator: `0xFF`
- Control codes: `FC / FD / F8 / F9 / F7` = multi-byte (2–3 bytes)
- Pointers: 32-bit LE, base `0x08000000`
- Main text: `0x1F00000–0x1F80000`
- `FA`/`FB` are NOT translation tokens
- `{LV}` = `0x34` | `{COLOR}X` → `FC 01 NN`
- Duplicate offsets in `combined_fr.txt`: last entry wins (~957 duplicates)

## Architecture constraints

1. All shared Python logic in `src/core/` — never copy-paste between scripts.
2. `input/` files are read-only sources; all output goes to `output/`.
3. Always write `*.gba.bak` before patching a ROM.
4. No Python scripts at the project root.
5. Numbered docs only: `docs/NN_NAME.md`.
6. Commit format: `type(scope): description` (no trailers, no `--no-verify`).

## emulator-web

Express 5 + `ws` WebSocket bridge to mGBA-WASM in Chromium.
Routes in `src/api.ts`, server wiring in `src/server.ts`.
Port = `process.env.EMULATOR_PORT ?? 3000`.
