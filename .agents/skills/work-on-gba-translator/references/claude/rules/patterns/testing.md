# Tests

## Commandes (via Makefile)

```bash
make test            # alias de test-python-fast
make test-python-fast # pytest rapide : unit, sans benchmarks/e2e/slow/stress/emulator/rom
make test-python     # pytest standard : -m "not emulator and not stress and not benchmark and not rom" -v
make test-vitest     # Vitest dans emulator-web/
make test-playwright # Playwright E2E (boot, gameplay, translation, visual-regression)
make test-all        # python-fast + vitest + playwright
```

Commande brute rapide : `python3 -m pytest tests/ -x --ignore=tests/benchmarks
--ignore=tests/e2e -m "not slow and not stress and not emulator and not rom"`.

## Markers pytest (déclarés dans `pyproject.toml` / `pytest.ini`)

| Marker | Sens |
|--------|------|
| `benchmark` | benchmarks de performance |
| `stress` | tests longs (>30 min) |
| `slow` | tests lents (>30 s) |
| `emulator` | nécessite mGBA |
| `rom` | nécessite une ROM GBA réelle |

Décore tout test coûteux/à dépendance externe avec le marker adéquat pour qu'il sorte
du profil rapide. Layout : `tests/unit/`, `tests/e2e/`, `tests/e2e-playwright/`,
`tests/benchmarks/`, `tests/stress/` + `tests/conftest.py` pour les fixtures.

## Règle critique : 100 % de succès OBLIGATOIRE

- Un taux < 100 % est un **échec** (99,9 % n'est pas acceptable).
- **Interdit** : skip un test pour masquer un échec, fix hardcodé sur un offset précis,
  « c'est un cas limite ».
- En cas d'échec : investiguer la cause racine (bytes réels, structures, comparaison
  avec la ROM espagnole de référence), implémenter un fix **générique**, puis re-tester
  100 % du corpus.

## Traductions ajoutées : couverture unitaire obligatoire

Chaque ligne non vide ajoutée à `languages/<lang>/combined_<lang>.txt` doit avoir
dans **le même commit** une entrée dans `languages/<lang>/protected_entries.yaml`.
Cette entrée fixe l'offset et la valeur exactement résolue par la règle
**dernière occurrence gagnante** ; `tests/unit/test_translation_integrity.py` la
vérifie pour toutes les langues. Le garde `scripts/check_staged_translation_tests.py`
refuse le commit si cette couverture manque ou si la valeur du manifeste ne correspond
pas à la valeur live. Il ne remplace pas un test métier dédié lorsqu'un formatage, une
taille de cellule ou un comportement de ROM est en jeu : dans ce cas, ajouter aussi le
test ciblé approprié.

## Avant de conclure

- Le hook `pre-commit` versionné dans `.githooks/` (installer via `make hooks` ou
  `make install`) contrôle les traductions ajoutées, puis lance `make test-python-fast`
  et les tests Vitest. S'il échoue, le commit n'a pas lieu : corriger tous les tests,
  re-stager, puis recommitter. Ne le contourne **jamais** (voir `git-workflow.md`).
- Pour une feature touchant l'émulateur ou l'affichage en jeu, lance aussi les specs
  Vitest/Playwright concernées. Pour une sonde mGBA : sessions courtes + savestates,
  **ne jamais sauvegarder en jeu** (cela écrase la fixture `.sav` et casse les goldens
  Playwright).

## Multilingue (FR/IT/DE/Indie) — ne jamais tester une seule langue

`tests/unit/{fr,it,de,en}` et `tests/e2e/{fr,it,de,es}` sont tous sous `tests/` :
`make test` / `make test-python` les couvrent déjà **tous**. Un fix qui touche du
code partagé (`src/core/`, `scripts/build_language.py`, un script de patch réutilisé
sans suffixe `_<code>`) et n'est validé que par `pytest tests/unit/fr/` (ou un seul
fichier `*_fr.py`) n'est **pas** vérifié — lance la suite complète. Si le fix touche
la génération de ROM, rebuild aussi IT/DE (`make build-it && make build-de`) : les
tests unitaires utilisent des fixtures synthétiques, seul un rebuild réel détecte une
régression de ROM complète. Détails et checklist : [`multilang-regression.md`](multilang-regression.md).
