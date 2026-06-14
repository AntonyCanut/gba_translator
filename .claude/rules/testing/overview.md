# Testing rules — gba_translator

## Test stacks at a glance

| Layer | Framework | Location | When to run |
|---|---|---|---|
| Python unit + integration | **pytest** | `tests/` | Always (`python3 -m pytest tests/`) |
| TypeScript unit (emulator-web) | **Vitest** | `emulator-web/tests/` | Always (`cd emulator-web && npm test`) |
| E2E ROM verification | **Playwright** | `tests/e2e-playwright/` | After FR injection (`npm run test:e2e`) |

---

## Shared principles (all layers)

### AAA — Arrange, Act, Assert

Every test follows this structure without exceptions:

```python
# Python / pytest
def test_decode_accented_char(charmap):
    # Arrange
    raw = bytes([0x06, 0xFF])          # É + terminator

    # Act
    result = decode_pokemon_text(raw)

    # Assert
    assert result == "É"
```

```typescript
// TypeScript / Vitest
it('decodes accented char', () => {
  // Arrange
  const data = new Uint8Array([0x06, POKEMON_TERMINATOR]);

  // Act
  const result = decodePokemonText(data);

  // Assert
  expect(result).toBe('É');
});
```

### No snapshot tests

- Do **not** use `toMatchSnapshot()` in Vitest or `assertSnapshot()` in pytest for logic tests.
- The only legitimate snapshots are **visual pixel diffs** in `tests/e2e-playwright/visual-regression.spec.ts` — Playwright screenshot baselines committed to `tests/e2e-playwright/snapshots/`.
- Snapshotting serialised objects or JSON is forbidden — write explicit `expect(result).toEqual({...})` assertions.

### 100 % suite must stay green

- Never skip tests to paper over a failure. A skipped test is a hidden bug.
- If a test is flaky (e.g., timing-sensitive Playwright scenario), fix the timing — do not add `.skip`.
- A red test suite blocks the commit; fix the root cause before committing.

---

## pytest (Python)

### Test markers

| Marker | Meaning |
|---|---|
| *(none)* | Fast unit test — no ROM, no emulator |
| `@pytest.mark.slow` | >30 s — excluded from quick CI runs |
| `@pytest.mark.emulator` | Requires mGBA running |
| `@pytest.mark.rom` | Requires a `.gba` file |
| `@pytest.mark.stress` | Long stress/soak test |

### Fixtures — real data, no mocks

- Use `conftest.py` fixtures that load **real binary ROM slices** (mini-fixtures in `tests/unit/fixtures/`), not mocked `MagicMock` objects.
- Never mock `ROMReader` — its mmap behaviour matters; test against a real fixture ROM or a synthetic binary `bytearray`.
- No `unittest.mock.patch` on internal I/O unless you own the boundary (e.g., patching `sys.stdin`).

### File placement

```
tests/
  unit/          Pure-Python tests, no ROM required
  e2e/           mGBA integration tests (@emulator)
  benchmarks/    Performance benchmarks
  stress/        Long-running stress tests
  conftest.py    Shared fixtures
```

### Running

```bash
# Fast (unit only, no ROM, no emulator)
python3 -m pytest tests/ --ignore=tests/benchmarks --ignore=tests/e2e -m "not slow and not stress and not emulator"

# Standard CI (unit + integration, no emulator)
python3 -m pytest tests/ -m "not emulator and not stress and not benchmark" -v

# Full
python3 -m pytest tests/ -v
```

---

## Vitest (TypeScript — emulator-web)

### File naming

- Test files live in `emulator-web/tests/` and are named `*.test.ts`.
- Import from `../src/<module>.js` (ESM-style with `.js` extension).

### Assertions

- Use `expect(result).toBe(...)` for primitives, `expect(result).toEqual(...)` for objects/arrays.
- Never use `toMatchSnapshot()` — write explicit assertions.
- Test one behaviour per `it()` block; keep `describe` groups flat (one level deep).

### userEvent — not applicable here

The emulator-web tests deal with binary data and HTTP/WebSocket, not DOM events. Skip `@testing-library/user-event`. If a future DOM layer is added, use `userEvent` exclusively (never `fireEvent`).

### getByRole — not applicable here

No DOM rendering in the emulator-web unit tests. If a DOM layer is added, prefer `getByRole` over `getByTestId` or CSS selectors.

### Running

```bash
cd emulator-web
npm test         # vitest run (single pass)
npm run test:watch  # vitest watch
```

---

## Playwright (E2E)

### What the tests verify

Playwright drives Chromium against the Express server (`emulator-web/`), which serves mGBA-WASM loaded with `GenedRom-fr.gba`. Tests assert:

1. The ROM boots without crash.
2. French text appears correctly (no mojibake, no English leakage).
3. Visual regression baselines match within 5 % pixel diff.

### Test projects

| Project | Spec | Purpose |
|---|---|---|
| `boot` | `boot.spec.ts` | ROM starts, title screen appears |
| `gameplay` | `gameplay.spec.ts` | Basic navigation, saves |
| `translation` | `translation.spec.ts` | FR strings correct |
| `visual-regression` | `visual-regression.spec.ts` | Screenshot baselines |

### Locators

- Prefer `page.getByRole(...)` and `page.getByText(...)` over CSS selectors.
- Use `page.locator('[data-testid=...]')` only when semantic locators are unavailable in the WASM canvas context.

### Input / interaction

- All GBA button presses go through the WebSocket Lua bridge (`commands.ts`), not `page.keyboard`.
- Never use `page.mouse.click()` for game input — use the API layer.

### No in-game saves

**Never call the in-game save function during tests.** It overwrites the `.sav` fixture and corrupts Playwright golden baselines. Use save-state snapshots via the Lua bridge instead.

### Visual baselines

- Baselines live in `tests/e2e-playwright/snapshots/`.
- Update with: `npm run test:e2e:update-snapshots`
- Committed to git — treat them as test fixtures; review diffs carefully.
- `maxDiffPixelRatio: 0.05` (5 %) is the threshold; tighter is better.

### Running

```bash
npm run test:e2e                  # all projects
npm run test:e2e:boot             # boot only
npm run test:e2e:translation      # translation checks only
```

---

## Anti-patterns (forbidden)

| Pattern | Why |
|---|---|
| `unittest.mock.patch` on `ROMReader` internal methods | Hides real encoding bugs |
| `toMatchSnapshot()` on JSON/text in Vitest | Brittle; hides regressions as "just update the snapshot" |
| `fireEvent` in future DOM tests | Use `userEvent` — it simulates real browser events |
| `.skip` or `xfail` to silence a failing test | Hidden bugs ship |
| Hard-coding offsets in tests | Tests break when ROM layout changes; use fixture data |
| Saving the game during Playwright tests | Corrupts `.sav` fixture; breaks golden baselines |
