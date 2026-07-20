---
name: unbound-ci-missing-pyyaml-dep
description: build-it/build-de KO en CI (ModuleNotFoundError yaml) car pyyaml absent de pyproject.toml dependencies ; local OK le masque
metadata:
  node_type: memory
  type: project
  originSessionId: e58e73df-543f-41c2-a6c0-3ac269c543f4
---

B-84 (suite) : une fois le build FR réparé (patch_worldmap_labels_fr commit f1d71ce
livrant 0xB500A0 "Bourg Gurun" / 0xB535C8 "Île de la Lune" / 0x1F49B76 Dresco), le
workflow CI restait rouge sur le gate « Fail if Italian ROM was not delivered ».

**Cause racine** : `make build-it` (et build-de) → `scripts/build_language.py` →
`src/i18n/registry.py` fait `import yaml`. Or `pyproject.toml` déclarait
`dependencies = []`. CI installe via `pip install -e ".[dev]"` → PyYAML jamais
installé → `ModuleNotFoundError: No module named 'yaml'`. `continue-on-error: true`
sur l'étape Italian avalait l'échec (conclusion=success mais **outcome=failure**),
donc `verify_it` (`if: build_it.outcome == 'success'`) était **skipped**, et le gate
final `build_it.outcome != 'success' || verify_it.outcome != 'success'` faisait
échouer tout le job APRÈS que la FR ait été release.

**Piège** : la machine du dev a PyYAML installé globalement → `make build-it` marche
en local → l'écart CONFIRME le diagnostic « il manque un truc pour que le workflow
fonctionne comme le build local » = la dépendance déclarée. Le CLAUDE.md appelle même
pyyaml « the only external dependency » alors qu'elle n'était pas dans pyproject.

**Fix** : `dependencies = ["pyyaml>=6.0"]` + garde `tests/test_packaging_dependencies.py`
(tomllib en 3.11 CI / fallback regex en 3.9 hook local). Vérifié : `make build-it`
EXIT 0 bout-en-bout + `verify_version_display.py --lang-code it` OK.

Lié : [[unbound-fr-build-lives-in-gba-translator]] [[unbound-multilang-build-registry]]
[[unbound-prepare-fr-json-clobbers-dedicated-patches]] [[singularity-build-resets-worktree]]
Diag CI : lire `gh run view <id> --json jobs` (conclusion vs outcome des steps
continue-on-error) pour trouver QUEL step casse, pas seulement le dernier rouge.
