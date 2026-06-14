# Testing — gba_translator (Codex)

## Test stacks

| Layer | Framework | Command |
|---|---|---|
| Python unit/integration | pytest | `python3 -m pytest tests/ -m "not emulator and not stress and not benchmark" -v` |
| TypeScript unit | Vitest | `cd emulator-web && npm test` |
| E2E ROM verification | Playwright | `npm run test:e2e` |

## AAA pattern (all layers)

```python
def test_encode_accented():
    # Arrange
    text = "É"
    # Act
    result = encode_pokemon_text(text)
    # Assert
    assert result == bytes([0x06, 0xFF])
```

```typescript
it('encodes accented char', () => {
  // Arrange + Act + Assert
  expect(encodePokemonText('É')).toEqual(new Uint8Array([0x06, 0xFF]));
});
```

## pytest rules

- Real binary fixtures only — no `unittest.mock.patch` on `ROMReader`.
- Markers: `slow`, `emulator`, `rom`, `stress`, `benchmark`.
- No `.skip` / `xfail` to hide failures — 100 % pass required.
- Fixture ROM slices live in `tests/unit/fixtures/`.

## Vitest rules

- Files: `emulator-web/tests/*.test.ts`.
- No `toMatchSnapshot()` — explicit `toEqual()` assertions.
- One behaviour per `it()`. Flat `describe` (one level).
- `userEvent` only if a DOM layer is ever added (currently not applicable).
- `getByRole` first if a DOM layer is added.

## Playwright rules

- Locators: prefer `getByRole`, `getByText`.
- GBA input via WebSocket Lua bridge — never `page.keyboard`.
- **Never in-game save** during tests — corrupts `.sav` fixture and breaks golden baselines.
- Visual baselines in `tests/e2e-playwright/snapshots/` are committed artefacts.
- `maxDiffPixelRatio: 0.05` threshold.

## Forbidden patterns

| Pattern | Reason |
|---|---|
| Mock `ROMReader` | Hides real encoding bugs |
| `toMatchSnapshot()` on logic output | Brittle; regressions become "snapshot updates" |
| `.skip` / `xfail` on failures | Hidden bugs ship |
| Hard-coded ROM offsets in test assertions | Breaks when layout changes |
| In-game save during Playwright tests | Corrupts `.sav` fixture |
