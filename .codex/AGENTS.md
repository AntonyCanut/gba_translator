# gba_translator — Codex context (.codex/AGENTS.md)

See `/AGENTS.md` at the repo root for the full Codex AI memory.

## Quick reference

| Task | Command |
|---|---|
| Build FR ROM | `make build-fr` |
| Fast tests | `make test` |
| Full pipeline | `make pipeline` |
| Charmap sync check | `make sync-charmap-check` |

## Key files

- Main build engine: `src/translators/19_build_translated_rom_generic.py`
- Charmap: `src/core/text_codec.py` (POKEMON_TABLE)
- Master translation: `combined_fr.txt` (last entry wins on duplicates)
- Project rules: `.claude/project-rules.md`
