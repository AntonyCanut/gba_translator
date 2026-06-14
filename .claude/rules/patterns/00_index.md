# Patterns de code — gba_translator

Guides de style par domaine, dérivés du **code réel** du dépôt. Tout agent (Claude,
Codex, Ollama) DOIT coder comme le reste du projet en respectant ces fichiers.

> La source de vérité architecturale historique reste [`../../project-rules.md`](../../project-rules.md).
> Les fichiers de ce dossier la complètent avec le style concret observé dans `src/`, `scripts/` et `tests/`.

| Fichier | Domaine |
|---------|---------|
| [`python.md`](python.md) | Style Python : type hints, docstrings, OOP, dataclasses |
| [`architecture.md`](architecture.md) | Disposition `input/`/`output/`/`src/core`, DRY, flux pipeline |
| [`scripts-pipeline.md`](scripts-pipeline.md) | Scripts numérotés `NN_*.py`, `scripts/`, argparse, Makefile |
| [`text-encoding.md`](text-encoding.md) | Charmap Gen III, terminateurs, control codes, pointeurs |
| [`testing.md`](testing.md) | pytest, markers, profils, 100 % de succès, Vitest/Playwright |
| [`tooling.md`](tooling.md) | ruff, hook pre-commit, `sync-charmap`, CI |
| [`naming.md`](naming.md) | Nommage fichiers / classes / fonctions / constantes |
| [`forbidden.md`](forbidden.md) | Patterns interdits |
| [`git-workflow.md`](git-workflow.md) | Branches, format de commit, worktrees, hooks |

**Langue** : code et commentaires en français (le projet entier est francophone).
Les identifiants Python restent en `snake_case`/`PascalCase` anglais, les docstrings
et commentaires sont en français.
