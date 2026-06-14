# Architecture — gba_translator

## Project purpose

GBA ROM translation toolkit for Pokémon Unbound (CFRU/BPRE01).
Converts the English ROM to French by patching the proprietary Gen III text encoding,
pointer tables, and binary regions without touching the game engine.

## Language stack

| Layer | Runtime | Entry points |
|---|---|---|
| Translation pipeline | Python 3.11+ | `scripts/`, `src/` |
| Web emulator server | Node 20 / TypeScript | `emulator-web/src/server.ts` |
| E2E test runner | Playwright (Node) | `tests/e2e-playwright/` |
| Unit tests (TS) | Vitest | `emulator-web/tests/` |
| Unit/integration tests (Py) | pytest | `tests/` |

## Python source layout (`src/`)

```
src/
  core/          ROM I/O, text codec, padding detector, reinserter, validator
  text/          CFRU charmap data, encoder/decoder
  extractors/    String finder, dump formats
  translators/   CSV/JSON pipeline, space manager, injector
  cooker/        mGBA automation, checkpoint, crash diagnosis
  analyzers/     Structure analysis tools
  commands/      CLI wrappers
  utils/         Shared helpers
  validators/    Pre/post-injection validators
```

### Key domain invariants

- **Encoding**: CFRU charmap (not ASCII). See `src/text/charmap_data.py`.
- **Terminator**: `0xFF` marks end of every string.
- **Control codes**: `FC / FD / F8 / F9 / F7` are multi-byte (2–3 bytes each).
- **Pointers**: 32-bit little-endian, base address `0x08000000`.
- **Main text region**: `0x1F00000–0x1F80000`.
- **Free space**: ~1.2 MB across 1,216 blocks post-injection.
- **French accents**: é è ê ë à â ç ù û ü î ï ô œ all supported; ê/ç/ù absent from the intro font.

### Core classes (never duplicate these)

| Class | File | Responsibility |
|---|---|---|
| `ROMReader` | `src/core/rom_reader.py` | mmap-based ROM I/O |
| `TextCodec` | `src/core/text_codec.py` | encode/decode CFRU bytes ↔ Unicode |
| `PaddingDetector` | `src/core/padding_detector.py` | measure free bytes after a string |
| `TextReinserter` | `src/core/text_reinserter.py` | write translated strings + update pointers |
| `FallbackTranslator` | `src/core/fallback_translator.py` | per-string length-aware wrapping |

## TypeScript emulator-web layout

```
emulator-web/
  src/
    server.ts     Express HTTP + WebSocket server (serves mGBA-WASM)
    api.ts        REST endpoints
    mgba-bridge.ts WebSocket bridge to running emulator
    charmap.ts    CFRU charmap (mirrors Python side)
    memory.ts     GBA memory read helpers
    commands.ts   Lua-command queue
  tests/          Vitest unit tests (see testing rules)
```

## Architecture rules

1. **No root-level scripts** — scripts go in `scripts/`, archived ones in `scripts/legacy/`.
2. **DRY** — shared logic lives in `src/core/`. Never copy functions between scripts.
3. **Inputs are read-only** — `englishrom.gba`, `spanishrom.gba` are never written to.
4. **Outputs are always regenerated** — all derived artefacts go under `output/`.
5. **Backups before patching** — always write `*.gba.bak` before modifying a ROM.
6. **One class per file** in `src/core/`. No mega-modules.
7. **Type hints everywhere** in Python; explicit return types in TypeScript.
8. **Numbered docs** — every file in `docs/` must be `NN_NAME.md`.
9. **Commit hygiene** — `type(scope): description`, no Co-Authored-By trailers, no --no-verify.

## Data-flow (translation pipeline)

```
englishrom.gba
  → extract text (src/extractors/)        → output/extracted/*.json
  → compare EN↔ES (src/extractors/)       → output/differences/*.json
  → translate (combined_fr.txt / CSV)
  → inject FR text (src/core/text_reinserter.py)
  → post-build patches (scripts/patch_*.py)
  → output/roms/GenedRom-fr.gba
  → Playwright e2e verification
```

## Web-emulator data-flow

```
GenedRom-fr.gba
  → emulator-web/src/server.ts  (Express serves mGBA-WASM)
  → Playwright → chromium → mGBA WASM in browser
  → WebSocket → mgba-bridge.ts → Lua commands
  → screenshot / memory read → test assertions
```
