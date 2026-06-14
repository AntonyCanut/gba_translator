# gba_translator — Claude project context

See `/CLAUDE.md` at the repo root for the full AI memory (stack, folder map,
commands, glossary, gotchas).

## Quick orientation

- **Build FR ROM**: `make build-fr`
- **Fast tests**: `make test`
- **Main translation file**: `combined_fr.txt` (last entry wins for duplicates)
- **Build engine**: `src/translators/19_build_translated_rom_generic.py`
- **Charmap**: `src/core/text_codec.py` — POKEMON_TABLE + FR accents

## Project rules

See `.claude/project-rules.md` for coding conventions (folder structure,
naming, 100% test pass rate requirement, commit format).
