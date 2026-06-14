---
name: test-driven-development
description: Use when implementing any feature or bugfix, before writing implementation code
when_to_use: New features, bug fixes, refactoring, behavior changes in gba_translator
---

# Test-Driven Development (TDD)

## Overview

Write the test first. Watch it fail. Write minimal code to pass.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

**Project rule:** 100% test pass rate is MANDATORY. No skips, no workarounds.

## Test Runner (gba_translator)

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/unit/test_<module>.py::test_name -v

# Run with coverage
pytest --cov=src tests/

# Run unit tests only
pytest tests/unit/

# Run integration tests only
pytest tests/integration/
```

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? Delete it. Start over.

## Red-Green-Refactor

### RED — Write Failing Test

Place test in `tests/unit/test_<module>.py` or `tests/integration/`.

```python
def test_decode_french_accent():
    encoder = PokemonEncoder()
    result = encoder.decode(bytes([0xAC]))  # é
    assert result == "é"
```

Run:
```bash
pytest tests/unit/test_text_encoder.py::test_decode_french_accent -v
```

Confirm: test FAILS because feature is missing, not due to a typo.

### GREEN — Minimal Code

Write the simplest possible implementation in `src/`:

```python
class PokemonEncoder:
    def decode(self, data: bytes) -> str:
        return CHARMAP.get(data[0], "?")
```

Run:
```bash
pytest tests/unit/test_text_encoder.py::test_decode_french_accent -v
```

Confirm: PASS. All other tests still pass (`pytest tests/`).

### REFACTOR — Clean Up

After green only:
- Remove duplication (DRY — extract to `src/core/`)
- Improve names (snake_case functions, PascalCase classes)
- Add type hints and docstrings (required by project-rules.md)

Keep tests green. Don't add behavior.

## Project Conventions

- Tests live in `tests/unit/` or `tests/integration/`
- Source code lives in `src/core/`, `src/text/`, `src/inject/`, etc.
- Test file naming: `test_<module>.py`
- Fixtures in `tests/` alongside test files
- Never mock ROM I/O unless testing at the boundary (prefer real fixture ROM bytes)

## Verification Checklist

Before marking work complete:

- [ ] Every new function/method has a test
- [ ] Watched each test fail before implementing
- [ ] Each test failed for expected reason (feature missing, not typo)
- [ ] Wrote minimal code to pass each test
- [ ] All tests pass: `pytest tests/` → 0 failures
- [ ] 100% pass rate (project-rules.md: this is mandatory)
- [ ] Output pristine (no errors, warnings)
- [ ] Docstrings + type hints added

Can't check all boxes? You skipped TDD. Start over.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Already manually tested" | Ad-hoc ≠ systematic. No record, can't re-run. |
| "99.9% is close enough" | Project-rules.md: 100% is mandatory. |
| "Skip for this offset edge case" | Never. Fix generically, not with hardcoded exceptions. |
