---
name: code-review
description: Review a diff against project rules and acceptance criteria before merging
when_to_use: After completing a task, implementing a feature, or before any merge to main
---

# Code Review

Check the diff against project conventions and the ticket's acceptance criteria. Flag gaps before merge.

## When to Review

- After each feature task or bugfix
- Before any merge to main
- When stuck (fresh perspective)
- After fixing a complex pipeline bug

## The Checklist

Run `git diff` or `git show` and verify every item below.

### 1. Project Structure Rules (from `.claude/project-rules.md`)

- [ ] No `.py` files at repo root (only `Makefile`, `README.md`, `requirements.txt`, `.gitignore`, configs)
- [ ] No `.md` files at root except `README.md`
- [ ] New scripts land in the correct `src/` subfolder (`extractors/`, `analyzers/`, `translators/`, `utils/`)
- [ ] Scripts in `src/` are numbered (`NN_name.py`)
- [ ] New docs land in `docs/` and are numbered (`NN_NAME.md`)
- [ ] All generated files go to `output/` with `YYYY-MM-DD_` prefix
- [ ] Input ROMs in `input/roms/` — never modified, never written to

### 2. Architecture and DRY

- [ ] Common code lives in `src/core/`, not duplicated across scripts
- [ ] New scripts import from `src/core/` — no copy-paste of existing logic
- [ ] Classes: PascalCase (`ROMReader`, `TextExtractor`)
- [ ] Functions: snake_case (`read_pointer`, `decode_text`)
- [ ] Constants: UPPER_SNAKE_CASE (`GBA_ROM_BASE`)

### 3. Code Quality

- [ ] All public functions/methods have docstrings with Args/Returns/Example
- [ ] Type hints present on all function signatures
- [ ] ROM loaded once and reused — not reloaded per operation
- [ ] No magic numbers — use named constants
- [ ] No hardcoded offsets as special cases (generic fix required)

### 4. Encoding / ROM Safety

- [ ] Text terminated with `0xFF`
- [ ] Pointers updated after any relocation
- [ ] Backup created (`.gba.bak`) before any ROM write
- [ ] Offsets validated before write
- [ ] French accented characters use correct charmap entries

### 5. Tests

- [ ] New functions/classes have corresponding tests in `tests/unit/` or `tests/integration/`
- [ ] Tests follow TDD (they were written BEFORE the implementation)
- [ ] No tests are skipped or marked `xfail` to hide failures
- [ ] `pytest tests/` passes with 0 failures and 0 errors (100% required)
- [ ] Edge cases and error paths are tested

### 6. Commit Format

```
type(scope): description courte

Description détaillée si nécessaire.
- Point 1
- Point 2
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

- [ ] Commit message follows conventional format
- [ ] No `Co-Authored-By` trailers
- [ ] One logical change per commit

## How to Review

```bash
# See all changes
git diff HEAD~1

# See changed files
git diff --stat HEAD~1

# Run full test suite
pytest tests/ -v

# Run with coverage
pytest --cov=src tests/
```

## Output Format

Report findings as:

**Critical** (blocks merge): wrong file location, skipped test, hardcoded offset fix, ROM modified without backup, missing 0xFF terminator

**Important** (fix before proceeding): missing docstring, missing type hint, duplicated code that should be in `src/core/`, magic number

**Minor** (note for later): naming inconsistency, comment clarity, overly long function

**Assessment**: Ready / Fix critical issues / Fix important issues

## Red Flags

- Script at repo root → block merge
- Skipped test → block merge
- `pytest tests/` shows failures → block merge
- Hardcoded `if offset == 0xABCDEF` → block merge (project-rules.md: forbidden)
- Missing backup before ROM write → block merge
