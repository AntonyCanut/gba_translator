# Testing — gba_translator (Ollama)

## Test stacks

| Framework | Layer | Location | Command |
|---|---|---|---|
| pytest | Python unit + integration | `tests/` | `python3 -m pytest tests/ -m "not emulator and not stress and not benchmark" -v` |
| Vitest | TypeScript unit (emulator-web) | `emulator-web/tests/` | `cd emulator-web && npm test` |
| Playwright | E2E ROM verification | `tests/e2e-playwright/` | `npm run test:e2e` |

## Core principle: AAA

Every test, in every framework, uses Arrange / Act / Assert:

```python
# pytest
def test_decode_terminator():
    raw = bytes([0xFF])          # Arrange
    result = decode(raw)          # Act
    assert result == ""           # Assert
```

```typescript
// Vitest
it('stops at terminator', () => {
  const data = new Uint8Array([0xBB, 0xFF]);  // Arrange
  const result = decodePokemonText(data);      // Act
  expect(result).toBe('A');                    // Assert
});
```

## pytest specifics

- Real binary fixtures only — no mocks on `ROMReader` or file I/O.
- Test markers: `slow`, `emulator`, `rom`, `stress`, `benchmark`.
- Marker `emulator` = requires mGBA running; always exclude in CI unless emulator is available.
- 100 % pass rate required before commit. No `.skip`, no `xfail`.

## Vitest specifics

- Files: `emulator-web/tests/*.test.ts`.
- No snapshot tests (`toMatchSnapshot` is forbidden for logic).
- One behaviour per `it()`. One `describe` level.
- If a DOM layer is added: use `userEvent` exclusively (not `fireEvent`); prefer `getByRole` for locators.

## Playwright specifics

- Locators: `getByRole` > `getByText` > `locator('[data-testid=...]')`.
- GBA buttons via WebSocket Lua bridge only — never `page.keyboard`.
- Never trigger an in-game save — overwrites `.sav` fixture and invalidates visual baselines.
- Golden screenshots live in `tests/e2e-playwright/snapshots/`; update with `npm run test:e2e:update-snapshots`.
- Pixel-diff threshold: 5 % (`maxDiffPixelRatio: 0.05`).

## What NOT to do

| Anti-pattern | Why it's wrong |
|---|---|
| Mock `ROMReader` | Hides real binary-encoding bugs |
| Snapshot serialised JSON | Diffs hide intent; becomes "just update it" |
| `.skip` / `xfail` for failures | Ships hidden bugs |
| Hard-coded ROM offsets in assertions | Breaks if ROM layout shifts |
| In-game save during E2E tests | Corrupts `.sav`; breaks golden baselines |
| `fireEvent` instead of `userEvent` | Does not simulate real browser events |
