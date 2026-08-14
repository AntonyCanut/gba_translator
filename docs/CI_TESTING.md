# Infrastructure CI & Pyramide de tests

## Pyramide de tests

| Niveau       | Dossier              | Durée cible | Description                                       |
| ------------ | -------------------- | ----------- | ------------------------------------------------- |
| Unit         | `tests/`             | < 30s       | Tests unitaires sans ROM ni émulateur              |
| Integration  | `tests/`             | < 2min      | Tests ROM locaux après matérialisation BPS          |
| E2E          | `tests/e2e/`         | < 10min     | Pipeline complet, validation ROM traduite          |
| Stress       | `tests/` (`-m stress`) | > 30min   | Soak tests, fuzzing, endurance                     |
| Benchmarks   | `tests/benchmarks/`  | < 5min      | Performance injection, allocation, pipeline        |

## Markers pytest

| Marker       | Signification                                        |
| ------------ | ---------------------------------------------------- |
| `benchmark`  | Benchmarks de performance                            |
| `stress`     | Tests de stress (très long)                          |
| `slow`       | Tests lents (> 30s)                                  |
| `emulator`   | Nécessite mGBA sur le PATH                           |
| `rom`        | Nécessite la source locale puis les cibles BPS         |

## Variables d'environnement

| Variable                     | Description                                  |
| ---------------------------- | -------------------------------------------- |
| `GBA_TEST_ROM`               | Chemin vers la ROM GBA pour les tests        |
| `GBA_TEST_TRANSLATIONS_JSON` | Chemin vers le fichier JSON de traductions   |

## Commandes

```bash
# Unit tests uniquement (rapide, pas de ROM)
python3 -m pytest tests/ -x --ignore=tests/benchmarks --ignore=tests/e2e \
  -m "not slow and not stress and not emulator"

# CI standard (sans émulateur ni stress)
python3 -m pytest tests/ -m "not emulator and not stress and not benchmark" -v

# Pipeline complet
python3 -m pytest tests/ -v

# Benchmarks (avec sortie timing)
python3 -m pytest tests/benchmarks/ -v -s

# Stress tests
python3 -m pytest tests/ -m "stress" -v

# Avec ROMs matérialisées localement depuis les patchs suivis
make materialize-test-roms
make test-rom
```

## CI sans ROM

GitHub Actions ne possède aucun secret, téléchargement ou artefact ROM. Elle
exécute les profils pytest sans marker `rom`, Vitest et la validation
structurelle de `patches/`. Les tests ROM et Playwright sont locaux :

```bash
make test-rom
make test-playwright
```

Ces commandes appliquent les BPS à `input/roms/englishrom.gba` avant de
consommer les cibles sous `output/roms/`.

## Stratégie mGBA headless

Pour les tests E2E nécessitant mGBA :

- **mGBA 0.11+** : utiliser `mgba-sdl --script` en mode headless
- **Docker + Xvfb** : pour CI sans display
  ```bash
  xvfb-run mgba-sdl --script test_script.lua rom.gba
  ```
- Les tests marqués `@pytest.mark.emulator` sont automatiquement skippés si mGBA n'est pas disponible

## Structure des fichiers de test

```
tests/
  conftest.py              # Markers globaux, fixtures ROM/mGBA
  test_*.py                # Tests unitaires
  benchmarks/
    conftest.py            # Fixtures benchmark (ROM mémoire, timer)
    test_injection_perf.py # Performance injection texte
    test_allocation_perf.py# Performance allocation espace libre
    test_pipeline_perf.py  # Performance pipeline complet
  e2e/
    conftest.py            # Fixtures E2E
    test_*.py              # Tests end-to-end
```
