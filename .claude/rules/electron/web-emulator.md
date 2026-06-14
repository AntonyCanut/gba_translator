# Web Emulator — gba_translator

> This project does NOT use Electron. The browser-based emulator is a plain
> Express + WebSocket server (`emulator-web/`) that serves mGBA compiled to
> WASM. These rules cover that layer.

## Stack

| Piece | Technology |
|---|---|
| HTTP server | Express 5 |
| Real-time bridge | `ws` WebSocket |
| Emulator | mGBA compiled to WASM, loaded in Chromium via Playwright |
| Scripting | Lua commands sent over WebSocket |
| Unit tests | Vitest (see testing rules) |
| E2E tests | Playwright (see testing rules) |
| Language | TypeScript (strict mode, ESM modules) |

## TypeScript conventions

- `"type": "module"` in `package.json` — use `.js` extensions on relative imports after transpilation.
- Strict TypeScript (`tsconfig.json` enforces `strict: true`).
- Explicit return types on all exported functions and class methods.
- No `any` — use `unknown` + type guards when the shape is genuinely unknown.

## Express server rules

1. All routes are defined in `src/api.ts`; `src/server.ts` only wires them.
2. Return typed JSON responses — define interfaces next to the route, not inline.
3. No business logic in route handlers — delegate to `src/memory.ts`, `src/commands.ts`, etc.
4. Port is read from `process.env.EMULATOR_PORT ?? 3000`; never hard-coded.

## WebSocket / mGBA bridge

- The bridge lives in `src/mgba-bridge.ts`. One instance per server process.
- Lua commands are queued; never fire-and-forget on a command that modifies state.
- Always await the `ACK` from mGBA before reading memory back.
- Lua queue: `FA`/`FB` control bytes are **outside** the translation token queue — do not treat them as text tokens.

## mGBA WASM quirks

- `Aaaaaaa` / `Fffffff` names = button-mash artefacts from the naming screen; treat as no-op.
- Bridge cutoffs after long dialogue sequences are flakiness (timing), not crashes.
- Keep emulator sessions short; use save-states for reproducible test starting points.
- **Never save the game from inside the emulator during tests** — it overwrites the `.sav` fixture and breaks Playwright golden snapshots.

## ROM path

`ROM_PATH` env var → `output/roms/GenedRom-fr.gba` by default. Never hard-code a ROM path in source.

## Build

```bash
cd emulator-web
npm run build    # tsc → dist/
npm run dev      # tsx src/server.ts (watch mode)
```
