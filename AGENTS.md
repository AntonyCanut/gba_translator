# gba_translator — AI Memory (Codex / AGENTS.md)

> Pokemon Unbound GBA ROM toolkit: reverse-engineers English + Spanish ROMs and
> produces a French ROM translation (CFRU / BPRE01 engine).

## Stack

- Python 3.11+ (main language)
- GNU Make (build automation)
- pytest (unit + integration tests, markers: `emulator`, `rom`, `slow`, `stress`, `benchmark`)
- Playwright + TypeScript (E2E tests against mGBA emulator)
- Vitest (TypeScript unit tests for `emulator-web/`)
- pyyaml ≥ 6.0 (only external Python dep)

## Rules

### Architecture

- **DRY**: shared Python logic lives in `src/core/`. Never copy functions between scripts.
- No Python scripts at the project root. Scripts belong in `scripts/`; archived ones in `scripts/legacy/`.
- Inputs (`englishrom.gba`, `spanishrom.gba`) are read-only. All derived outputs go under `output/`.
- Write `output_path + ".bak"` before patching any ROM.
- Numbered docs: every file in `docs/` must match `NN_NAME.md`.
- Commit format: `type(scope): description` — no Co-Authored-By trailers, no `--no-verify`.

### Key domain invariants

- CFRU charmap (not ASCII) — see `src/text/charmap_data.py`.
- String terminator: `0xFF`.
- Control codes `FC / FD / F8 / F9 / F7` are multi-byte (2–3 bytes).
- Pointers: 32-bit little-endian, base `0x08000000`.
- Main text region: `0x1F00000–0x1F80000`.
- French chars: é è ê ë à â ç ù û ü î ï ô œ (all supported; ê/ç/ù absent from intro font).
- `FA`/`FB` bytes are outside the translation token queue — do not treat as text.
- `{LV}` = `0x34`; `{COLOR}X` → `FC 01 NN`.

### Testing

**Always run `detect_test_processes` before starting any test suite.**

#### Python (pytest)

- Test files live under `tests/`. Run: `python3 -m pytest tests/ -m "not emulator and not stress and not benchmark" -v`
- Use real binary fixtures (ROM slices in `tests/unit/fixtures/`) — never mock `ROMReader`.
- Follow **AAA** (Arrange / Act / Assert) strictly.
- No `unittest.mock.patch` on internal ROM I/O.
- No `.skip` or `xfail` to silence failures — fix the root cause.
- 100 % pass rate required before committing.

#### TypeScript (Vitest — emulator-web)

- Tests live in `emulator-web/tests/`. Run: `cd emulator-web && npm test`
- Follow **AAA** pattern.
- No `toMatchSnapshot()` for logic tests — write explicit `expect(result).toEqual(...)` assertions.
- One behaviour per `it()` block; `describe` groups are one level deep.

#### E2E (Playwright)

- Tests live in `tests/e2e-playwright/`. Run: `npm run test:e2e`
- Prefer `page.getByRole(...)` and `page.getByText(...)` as locators.
- GBA input goes through the WebSocket Lua bridge, not `page.keyboard`.
- **Never trigger an in-game save during tests** — it overwrites the `.sav` fixture and breaks golden baselines.
- Visual baselines in `tests/e2e-playwright/snapshots/` are committed artefacts; update deliberately.

### Web emulator (emulator-web/)

- Express 5 + `ws` WebSocket bridge to mGBA-WASM.
- Port from `process.env.EMULATOR_PORT ?? 3000` — never hard-coded.
- Route logic in `src/api.ts`; `src/server.ts` only wires them.
- Await mGBA ACK before reading memory after any Lua command.
- `Aaaaaaa` / `Fffffff` player names = naming-screen button mash; treat as no-op.
- Session saves during tests corrupt `.sav` fixtures — always use save-states.

## Skills

Reusable agent procedures located in `.codex/skills/`. Invoke by reading the relevant SKILL.md.

| Skill | File | When to Use |
|---|---|---|
| `test-driven-development` | `.codex/skills/test-driven-development/SKILL.md` | Before writing any implementation code |
| `systematic-debugging` | `.codex/skills/systematic-debugging/SKILL.md` | On any bug, test failure, or unexpected behavior |
| `brainstorming` | `.codex/skills/brainstorming/SKILL.md` | Before new features or architectural changes |
| `code-review` | `.codex/skills/code-review/SKILL.md` | After completing a task, before merging |
| `verification-before-completion` | `.codex/skills/verification-before-completion/SKILL.md` | Before any "done" claim or commit |
| `writing-plans` | `.codex/skills/writing-plans/SKILL.md` | After brainstorming approval, before coding |

### Skill priority

1. **Process skills first**: `brainstorming` → `writing-plans` → `test-driven-development`
2. **Quality gates**: `verification-before-completion` before every completion claim
3. **Debugging**: `systematic-debugging` before proposing any fix
4. **Review**: `code-review` after each task or before merge

## Project layout

```
src/
  core/             # shared library — import from here, not from scripts
    rom_reader.py   — ROMReader (load/read/write ROM, pointer I/O)
    text_codec.py   — POKEMON_TABLE charmap encode/decode
    text_reinserter.py — text injection + relocation
    dialogue_linewrap.py — 18-char dialogue wrap
    fixed_tables.py — addresses that must never be relocated
  extractors/
    pointer_text_extractor.py — scan ROM → extract text by pointer
  analyzers/
    11_pointer_text_diff.py — EN↔ES diff → offset map
  translators/
    19_build_translated_rom_generic.py — THE build engine (57 KB)
    28_export_trilingual_csv.py — EN/ES/FR CSV export
  validators/
    text_range_validator.py — byte-for-byte ROM validation
  cooker/
    emulator.py     — mGBA WebSocket launcher
    checkpoint.py   — savestate management for scenario tests

scripts/            # standalone CLI tools (not imported as modules)
  patch_font_fr.py              — add FR glyphs to font table
  patch_fixed_table_names.py    — patch hardcoded names (cities, NPCs)
  patch_time_format_fr.py       — Thumb code patch: DD/MM/YYYY, 24h
  apply_inline_overrides_fr.py  — inject inline text overrides
  repair_stable_lz77_blocks.py  — restore LZ77 graphics blocks
  repair_localized_lz77_blocks.py — restore localized LZ77 blocks
  repoint_stale_text_pointers.py — fix pointers after relocation
  spellcheck_combined_fr.py     — spellcheck combined_fr.txt
  audit_translation_fr.py       — quality audit (GOOD/ACCEPTABLE/BAD)
  sync_charmap.py               — sync Python charmap → TypeScript

tests/
  unit/             # fast tests, no ROM
  e2e/              # integration tests (need ROM files)
  e2e-playwright/   # Playwright E2E (need mGBA + ROM)
  benchmarks/       # slow benchmarks
  stress/           # very slow stress tests

emulator-web/       # TypeScript GBA emulator browser harness + Vitest tests

input/roms/         # source ROMs — READ ONLY, never modify
  englishrom.gba    — English source (BPRE01)
  spanishrom.gba    — Spanish reference translation

output/roms/        # build outputs: GenedRom-es.gba, GenedRom-fr.gba
combined_fr.txt     # master EN→FR translation (2 MB, last-entry-wins on duplicates)
```

## Canonical commands

```bash
# Install
make install                 # pip install -e ".[dev]" + npm install

# Build
make pipeline                # full EN→ES pipeline
make build-fr                # build French ROM (uses latest translation_ready.json)

# Test
make test                    # fast unit tests (no ROM/emulator)
make test-python             # unit + integration (no emulator)
make test-vitest             # Vitest (TypeScript emulator-web)
make test-playwright         # Playwright E2E (needs mGBA + ROMs)

# Quality
python3 scripts/audit_translation_fr.py
python3 scripts/spellcheck_combined_fr.py
make sync-charmap-check      # verify Python↔TypeScript charmap sync

# Lint / Coverage
ruff check .
pytest --cov=src tests/
```

## Project rules

- **No `.py` files at repo root** — scripts go in `src/extractors/`, `src/analyzers/`, etc.
- **No `.md` files at root except `README.md`** — docs go in `docs/NN_NAME.md` (numbered)
- **DRY via `src/core/`** — common code must live there, never duplicated
- **100% test pass rate** — failing or skipped tests block completion
- **Backups before ROM writes** — always create `.gba.bak`
- **Outputs → `output/`** — never write to `input/`
- Commit format: `type(scope): description` (feat, fix, refactor, docs, test, chore)

## Domain glossary

| Term | Meaning |
|---|---|
| `GBA_ROM_BASE` | `0x08000000` — all ROM pointers offset from here |
| `POKEMON_TERMINATOR` | `0xFF` — string terminator |
| `POKEMON_NEWLINE` | `0xFE` — line break |
| pointer | 32-bit LE; file offset = `value − 0x08000000` |
| charmap | `POKEMON_TABLE` in `text_codec.py`; space=`0x00`, A=`0xBB` |
| combined_fr.txt | Master `<hex_offset> <FR_text>` translation file |
| translation_ready.json | Structured JSON for build engine (in `output/translation/`) |
| offset map | EN→ES pointer mapping JSON |
| relocation | Moving text to free space when FR is longer |
| fixed table | ROM region that must not be relocated (species/move names) |
| LZ77 | GBA graphics compression; must be repaired after injection |
| mGBA | GBA emulator for E2E tests |

## Non-obvious rules

1. **combined_fr.txt**: ~957 duplicate offsets — last entry wins. Add entries at the bottom (lowercase block). Never use `csv.writer` (corrupts CRLF fields).
2. **Charmap sync**: After editing `text_codec.py`, run `make sync-charmap`.
3. **Fixed tables**: `src/core/fixed_tables.py` lists addresses that must never be relocated — relocation silently corrupts in-game lookups.
4. **LZ77**: Always run repair scripts after build-fr. `make build-fr` does this automatically.
5. **Stale pointers**: `repoint_stale_text_pointers.py` is mandatory at end of build.
6. **mGBA save**: NEVER save in-game during emulator tests — corrupts `.sav` fixture files.
7. **Intro font**: Glyphs `ê`, `ç`, `ù` missing from fullscreen intro font — avoid in intro text.
8. **Test markers**: `emulator` and `rom` must be excluded in CI (no ROM files on CI server).
9. **Positional placeholders**: `{0}`, `{1}` order must be preserved in FR strings.
10. **Gendered buffers**: Son/daughter via opcode 85. Use "mon enfant" not "mon {fille}".

## FR build sequence (what `make build-fr` does)

1. `19_build_translated_rom_generic.py` — main injection
2. `patch_font_fr.py` — add FR glyphs
3. `patch_fixed_table_names.py` — patch fixed names
4. `patch_time_format_fr.py` — Thumb code: DD/MM/YYYY, 24h
5. `apply_inline_overrides_fr.py` — inline text overrides
6. `repair_stable_lz77_blocks.py` — restore LZ77 images
7. `repair_localized_lz77_blocks.py` — restore localized LZ77
8. `repoint_stale_text_pointers.py` — fix stale pointers

## Conventions

> Source de vérité détaillée : `.claude/project-rules.md` et
> `.claude/rules/patterns/`. Codex DOIT s'y conformer — résumé ci-dessous.

### Structure
- `input/roms/` = **lecture seule** (`englishrom.gba`, `spanishrom.gba`), jamais modifiée.
- Tout artefact généré va dans `output/` (`roms/`, `extracted/`, `differences/`,
  `analysis/`, `reports/`, `translation/`), nommé `YYYY-MM-DD_description.ext`.
- Code réutilisable dans `src/core/` (classes) ; scripts d'étape numérotés `NN_*.py`
  dans `src/{extractors,analyzers,translators,validators}/` ; outils & patchs post-build
  dans `scripts/`. Docs numérotées `NN_NOM.md` dans `docs/`.
- **Racine** : uniquement `README.md`, `Makefile`, `pyproject.toml`, `pytest.ini`, la
  couche E2E (`package.json`, `tsconfig*.json`, `playwright.config.ts`), `combined_fr.txt`,
  `.gitignore`, et les fichiers de config d'assistant (`AGENTS.md`, `CLAUDE.md`). **Aucun**
  `.py` ni markdown de travail à la racine.

### Code
- Python : `snake_case` fonctions, `PascalCase` classes, `UPPER_SNAKE_CASE` constantes,
  type hints partout, docstrings Google **en français** sur l'API publique, `pathlib.Path`,
  offsets en hexadécimal. OOP + DRY (factoriser dans `src/core/`). Quasi-stdlib : ne pas
  ajouter de dépendance sans nécessité.
- Encodage **Gen III** (pas ASCII) : terminateur `0xFF`, newline `0xFE`, control codes
  `FC/FD/F8/F9/F7` multi-octets, pointeurs 32-bit LE base `0x08000000`. Toute modif de
  `src/core/text_codec.py` → `make sync-charmap` + `make sync-charmap-check`.
- TypeScript : `tsconfig` strict ES2022 ; tests Vitest (émulateur) / Playwright (E2E).

### Outillage
- Linter **ruff** (config par défaut) ; pas de formateur imposé. `ruff check` doit passer.
- Hook `pre-commit` (`.git/hooks/pre-commit`) : `py_compile` + `ruff` + pytest rapide sur
  les `.py` stagés. **Ne jamais le contourner** (`--no-verify`, `HUSKY=0`… interdits).

### Tests
- `make test` (rapide) / `make test-python` (standard) / `make test-vitest` /
  `make test-playwright`. Markers : `benchmark`, `stress`, `slow`, `emulator`, `rom`.
- **100 % de réussite obligatoire** : pas de skip, pas de fix hardcodé sur un offset ;
  investiguer la cause racine, fix générique, re-tester tout le corpus.

### Git
- Conventional Commits **en français** : `type(scope): description` (`feat`, `fix`,
  `refactor`, `docs`, `test`, `chore`, `ci`, `build`). Scopes : `core`, `translation`,
  `patch`, `pokedex`, `inline`, `rom`, `ai`…
- **Jamais** de trailer `Co-Authored-By`. **Jamais** contourner le hook. Historique
  **linéaire** : `git rebase` only, pas de `git merge` ni `git pull` sans `--rebase`.
- Branche de travail orchestré : `worktree/<slug>` ; intégration par rebase sur `unbound`.

## Capacités Codex activées

- **Multitâche** : isolation par worktree `.singularity-worktrees/<task-id>/`, verrou
  `.singularity-session.lock`, ports émulateur non partagés. Sérialiser les tâches qui
  buildent une ROM ou lancent l'émulateur ; paralléliser librement la lecture/analyse.
  Détail : `.claude/rules/multitasking.md`.
- **Hooks de cycle de vie** : voir `.codex/config.toml` (`[hooks]`) — garde-fous
  pré-commande (bloque contournement de hook / merge / écriture ROM source) et lint ruff
  post-édition, scripts dans `.codex/hooks/`.
- **Skills réutilisables** : `.codex/skills/` (procédures projet) ; ordre de découverte
  plugins → projet → rédaction fraîche. Voir `.codex/skills/README.md`.
