# Python conventions — gba_translator

## Style & tooling

- Python 3.11+; enforce with `pyproject.toml`.
- Formatter: **ruff** (configured in `pyproject.toml`); run `ruff check .` before committing.
- Type annotations mandatory on all public functions and class methods.
- Docstrings required on every public class, method, and module-level function.

## Naming

| Entity | Convention | Example |
|---|---|---|
| Module | `snake_case` | `text_codec.py` |
| Class | `PascalCase` | `TextReinserter` |
| Function / method | `snake_case` | `read_pointer()` |
| Constant | `UPPER_SNAKE_CASE` | `GBA_ROM_BASE = 0x08000000` |
| Private | leading `_` | `_decode_control()` |

## Imports

- Standard-library imports first, then third-party (`pyyaml`), then internal (`from src.core.rom_reader import ROMReader`).
- Never use star imports (`from module import *`).
- Import from `src.core.*` — do not duplicate shared logic.

## Error handling

- Raise specific exceptions (`ValueError`, `IOError`), not bare `Exception`.
- Validate ROM offsets before any write; raise `ValueError` with a clear message on out-of-bounds.
- Never silently swallow exceptions.

## Comments

- Explain **why**, not **what**.
- One short line max; no multi-paragraph comment blocks.
- Acceptable: `# GBA pointers include the ROM base; strip it before use`.

## Performance rules

1. Load ROM once; reuse the `ROMReader` instance throughout a script.
2. Cache computed charmap look-ups in a module-level dict — never recompute per character.
3. Use `mmap` for ROM access (already done in `src/core/rom_reader.py`).
4. Show progress bars (tqdm or manual) for operations over thousands of strings.

## Security / safety

1. Always write `output_path + ".bak"` before patching a ROM.
2. Validate every offset is within ROM bounds before writing.
3. Never modify files under `input/` — they are read-only sources.
