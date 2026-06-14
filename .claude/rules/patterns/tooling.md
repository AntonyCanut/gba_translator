# Outillage : formateur, linter, hooks, CI

## Linter — ruff

- Le linter en place est **ruff** (`.ruff_cache/` présent, invoqué par le hook
  pre-commit). Pas de `ruff.toml`/`.flake8`/`setup.cfg` dédié → **configuration par
  défaut de ruff**. `ruff check` doit passer sans erreur.
- Pas de formateur de code imposé (ni Black, ni Prettier côté Python). Respecter PEP 8
  tel que validé par ruff. Ne pas introduire un formateur sans demande explicite.

## Côté TypeScript (couche E2E + émulateur)

- `tsconfig.json` : `ES2022`, **strict**, `noEmit`. `typescript@^6`.
- Tests émulateur : **Vitest** (`emulator-web/`). E2E : **Playwright**
  (`playwright.config.ts`, tolérance visuelle `maxDiffPixelRatio` 0.05, snapshots dans
  `tests/e2e-playwright/snapshots/`). Pas d'ESLint/Prettier configuré à la racine.

## Hook pre-commit (`.git/hooks/pre-commit`) — NE JAMAIS contourner

Sur les fichiers `.py` stagés, le hook exécute dans l'ordre :
1. `py_compile` (vérif syntaxe) ;
2. `ruff check` ;
3. pytest rapide (`-x`, sans slow/stress/emulator/rom, hors benchmarks/e2e).

S'il échoue, le commit n'a **pas** eu lieu : corriger la cause, re-stager, recommettre.
Jamais `--no-verify`, `HUSKY=0`, ni édition du hook pour le neutraliser.

## CI (`.github/workflows/`)

Python 3.11 / Node 20 sur `ubuntu-latest`. Jobs : `python-tests-fast` (toutes PR),
`python-tests-standard` (push `master`), `charmap-sync` (vérifie la synchro charmap
Python↔TypeScript), `emulator-web-tests` (Vitest), `playwright-tests` (E2E).

## Outils Makefile

```bash
make sync-charmap        # régénère la charmap TypeScript depuis Python
make sync-charmap-check  # vérifie la synchro (dry-run, comme la CI)
make lint                # vérifie la collecte pytest
make install             # pip install -e ".[dev]" + npm install (+ emulator-web)
```
