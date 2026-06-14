# GBA ROM Translator — Codex Agent Instructions

## Project Overview

Python 3.11+ toolkit for translating Pokémon Unbound (CFRU/BPRE01) GBA ROMs from English to French.
Handles the proprietary Gen III text encoding, pointer management, and ROM patching.

## Test Runner

```bash
# All tests (596 collected, 100% pass rate required)
pytest tests/

# Unit tests only
pytest tests/unit/

# Integration tests (some require mGBA emulator)
pytest tests/integration/

# With coverage
pytest --cov=src tests/
```

## Project Rules Summary

- **No `.py` files at repo root** — scripts go in `src/extractors/`, `src/analyzers/`, etc.
- **No `.md` files at root except `README.md`** — docs go in `docs/NN_NAME.md` (numbered)
- **DRY via `src/core/`** — common code must live there, never duplicated
- **100% test pass rate** — failing or skipped tests block completion
- **Backups before ROM writes** — always create `.gba.bak`
- **Outputs → `output/YYYY-MM-DD_name.ext`** — never write to `input/`
- Commit format: `type(scope): description` (feat, fix, refactor, docs, test, chore)

## Skills

Reusable agent procedures located in `.codex/skills/`. Invoke by reading the relevant SKILL.md.

| Skill | File | When to Use |
|-------|------|-------------|
| `test-driven-development` | `.codex/skills/test-driven-development/SKILL.md` | Before writing any implementation code |
| `systematic-debugging` | `.codex/skills/systematic-debugging/SKILL.md` | On any bug, test failure, or unexpected behavior |
| `brainstorming` | `.codex/skills/brainstorming/SKILL.md` | Before new features or architectural changes |
| `code-review` | `.codex/skills/code-review/SKILL.md` | After completing a task, before merging |
| `verification-before-completion` | `.codex/skills/verification-before-completion/SKILL.md` | Before any "done" claim or commit |
| `writing-plans` | `.codex/skills/writing-plans/SKILL.md` | After brainstorming approval, before coding |

### Skill Priority

1. **Process skills first**: `brainstorming` → `writing-plans` → `test-driven-development`
2. **Quality gates**: `verification-before-completion` before every completion claim
3. **Debugging**: `systematic-debugging` before proposing any fix
4. **Review**: `code-review` after each task or before merge

## Key Technical Details

- **Encoding**: Proprietary CFRU charmap — see `src/text/charmap_data.py`
- **Terminator**: `0xFF` marks end of string
- **Control codes**: FC/FD/F8/F9/F7 are multi-byte (2-3 bytes)
- **Pointers**: 32-bit little-endian, base `0x08000000`
- **Main text region**: `0x1F00000–0x1F80000`
- **French chars**: é è ê ë à â ç ù û ü î ï ô œ (all accented)
