# Guide de test — GBA Translator

Ce document décrit l'ensemble du système de test du projet : couches, commandes, CI/CD, système de tickets automatiques et dépannage.

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Prérequis](#prérequis)
3. [Commandes rapides](#commandes-rapides)
4. [Tests Python (pytest)](#tests-python-pytest)
5. [Tests Emulator-web (Vitest)](#tests-emulator-web-vitest)
6. [Tests E2E Playwright](#tests-e2e-playwright)
7. [Système de tickets automatiques](#système-de-tickets-automatiques)
8. [CI/CD — GitHub Actions](#cicd--github-actions)
9. [Troubleshooting](#troubleshooting)

---

## Vue d'ensemble

Le projet utilise trois couches de tests complémentaires :

```
                    ┌────────────────────┐
                    │   Playwright E2E   │  Teste la ROM dans un émulateur
                    │   (navigateur)     │  via mGBA-wasm + serveur web
                    └────────┬───────────┘
                             │
                    ┌────────┴───────────┐
                    │   Vitest (Node)    │  Teste le décodage charmap,
                    │   emulator-web     │  mémoire, commandes GBA
                    └────────┬───────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
   ┌─────┴──────┐    ┌──────┴──────┐    ┌───────┴──────┐
   │   Unit     │    │ Integration │    │  Benchmarks  │
   │  (pytest)  │    │   (pytest)  │    │ / Stress     │
   └────────────┘    └─────────────┘    └──────────────┘
```

| Couche | Techno | Cible | Quand l'utiliser |
|--------|--------|-------|------------------|
| **Unit** | pytest | Codecs, pointeurs, réinserteur, LZ77 | Après chaque modification de la logique Python |
| **Integration / E2E Python** | pytest + mGBA | Flux gameplay, vérification traduction, qualité | Validation ROM locale (nécessite mGBA) |
| **Benchmarks** | pytest | Performances allocation, injection, pipeline | Avant/après optimisation de performance |
| **Stress** | pytest + mGBA | Fuzzing, épuisement mémoire, endurance (100k+ frames) | Validation de stabilité |
| **Vitest** | vitest | Charmap TypeScript, mémoire, commandes GBA | Après modification de `emulator-web/` |
| **Playwright** | Playwright + Chromium | ROM en live dans le navigateur, menus, combats, NPC | Tests de bout en bout de la traduction |

---

## Prérequis

### Python

- **Python 3.11+**
- Installer les dépendances : `pip install -e ".[dev]"`

### Node.js

- **Node.js 20+** avec npm
- Installer les dépendances :
  ```bash
  npm install                     # racine (Playwright)
  cd emulator-web && npm install  # émulateur web
  ```
- Ou tout d'un coup : `make install`

### Playwright

```bash
npx playwright install chromium
# ou
make install-playwright
```

### Variables d'environnement

| Variable | Usage | Valeur par défaut |
|----------|-------|-------------------|
| `GBA_TEST_ROM` | Chemin vers la ROM de test (pour pytest E2E / stress) | *(aucune — tests skippés si absente)* |
| `ROM_PATH` | Override du chemin ROM pour le serveur emulator-web | *(auto)* |
| `CI` | Détection CI (ajuste workers Playwright, retries) | *(auto par GitHub Actions)* |
| `BASE_URL` | URL du serveur émulateur pour Playwright | `http://localhost:3000` |
| `EMULATOR_PORT` | Port du serveur émulateur | `3000` |
| `ROM_NAME` | Nom de la ROM dans les rapports Playwright | `frenchrom.gba` |

---

## Commandes rapides

```bash
# Lancer les tests rapides (< 30s) — le défaut
make test

# Tests Python rapides (unit, sans benchmarks/stress/e2e/emulator)
make test-python-fast

# Tests Python standard (sans emulator/stress/benchmark)
make test-python

# Tests Vitest (emulator-web, < 5s)
make test-vitest

# Tests Playwright E2E (démarre le serveur automatiquement)
make test-playwright

# Tout d'un coup
make test-all

# Vérifier la synchronisation charmap Python → TypeScript
make sync-charmap-check

# Synchroniser la charmap
make sync-charmap

# Vérifier la collecte pytest (pas d'exécution)
make lint

# Lister les tickets auto-générés
make tickets

# Générer le rapport Playwright complet
make report
```

---

## Tests Python (pytest)

### Structure

```
tests/
├── conftest.py                         # Fixtures globales (rom_path, rom_data, mgba_available)
├── test_text_codec.py                  # Encodage/décodage CFRU
├── test_reinserter.py                  # Moteur de réinsertion de texte
├── test_reinserter_relocation.py       # Relocation de texte
├── test_builder_pointer_copy.py        # Copie de pointeurs ROM
├── test_control_placeholders.py        # Codes CFRU (pause, couleurs, variables)
├── test_dynamic_translation_insertion.py
├── test_font_patch.py                  # Patch de font française
├── test_inline_text_copy.py            # Copie inline
├── test_localized_lz77_blocks.py       # Décompression/réparation LZ77
├── test_pointer_text_extractor.py      # Extraction de texte par pointeur
├── test_regression_texts.py            # Régression textes connus
├── test_text_range_validator.py        # Validation de zones texte
│
├── e2e/                                # E2E Python (nécessite mGBA)
│   ├── data/quality_baseline.json
│   ├── test_content_accuracy.py        # Précision traduction vs ROM
│   ├── test_gameplay_flow.py           # Navigation gameplay avec EmulatorBridge
│   ├── test_quality_gates.py           # Portes qualité (octets inconnus, overflow)
│   └── test_translation_verification.py # Vérification croisée ROM/JSON
│
├── benchmarks/                         # Benchmarks de performance
│   ├── conftest.py                     # Fixtures : rom_32mb, sample_translations_*
│   ├── test_allocation_perf.py         # Throughput allocateur d'espace
│   ├── test_injection_perf.py          # Performance injection texte
│   └── test_pipeline_perf.py           # Pipeline complète
│
└── stress/                             # Tests de stress (longs)
    ├── conftest.py                     # Fixtures : en_rom_path, fake_rom, rom_copy
    ├── test_injection_fuzzing.py       # Fuzzing avec payloads aléatoires
    ├── test_pointer_exhaustive.py      # Pointeurs exhaustifs
    ├── test_soak.py                    # Endurance 100k+ frames (mGBA)
    └── test_space_exhaustion.py        # Épuisement de l'espace ROM
```

### Markers pytest

Définis dans `pytest.ini` et `pyproject.toml` :

| Marker | Description | Commande |
|--------|-------------|----------|
| `benchmark` | Benchmarks de performance | `pytest tests/benchmarks/ -v -s` |
| `stress` | Tests de stress (long, > 30 min) | `pytest tests/ -m "stress" -v` |
| `slow` | Tests lents (> 30 s) | inclus sauf dans le profil rapide |
| `emulator` | Nécessite mGBA installé | `pytest tests/ -m "emulator" -v` |
| `rom` | Nécessite une ROM GBA (`GBA_TEST_ROM`) | `pytest tests/ -m "rom" -v` |

### Profils d'exécution

| Profil | Commande | Quand |
|--------|----------|-------|
| **Rapide** | `pytest tests/ -x --ignore=tests/benchmarks --ignore=tests/e2e -m "not slow and not stress and not emulator"` | Développement local |
| **Standard** | `pytest tests/ --ignore=tests/benchmarks -m "not slow and not stress and not emulator"` | Validation locale |
| **CI** | `pytest tests/ -m "not emulator and not stress and not benchmark" -v` | CI/CD master |
| **Complet** | `pytest tests/ -v` | Avant release |
| **Benchmarks** | `pytest tests/benchmarks/ -v -s` | Mesure perf |
| **Stress** | `pytest tests/ -m "stress" -v` | Stabilité |

### Fixtures globales

Définies dans `tests/conftest.py` :

- **`rom_path`** *(session)* — Lit la variable `GBA_TEST_ROM`, skip le test si absente
- **`rom_data`** *(session)* — Charge la ROM en `bytearray`
- **`mgba_available`** *(session)* — Vérifie que `mgba` ou `mgba-sdl` est dans le PATH

---

## Tests Emulator-web (Vitest)

### Structure

```
emulator-web/
├── vitest.config.ts         # Config : include tests/**/*.test.ts
├── package.json             # Scripts : test, test:watch
├── tests/
│   ├── charmap.test.ts      # Décodage/encodage Pokémon, accents, contrôle
│   ├── commands.test.ts     # Instructions/commandes GBA
│   └── memory.test.ts       # Lecture/écriture mémoire
└── src/
    ├── charmap.ts            # Module charmap (généré par sync_charmap.py)
    ├── commands.ts
    └── memory.ts
```

### Commandes

```bash
# Exécution unique
cd emulator-web && npx vitest run
# ou
make test-vitest

# Mode watch (développement)
cd emulator-web && npx vitest
```

### Synchronisation charmap

La charmap TypeScript (`emulator-web/src/charmap.ts`) est générée à partir de la source Python. Pour vérifier qu'elles sont synchronisées :

```bash
make sync-charmap-check   # dry-run, détecte le drift
make sync-charmap          # applique la synchronisation
```

La CI vérifie automatiquement la synchronisation (job `charmap-sync`).

---

## Tests E2E Playwright

### Structure

```
tests/e2e-playwright/
├── boot.spec.ts                     # Démarrage ROM, savestates
├── gameplay.spec.ts                 # Scénarios gameplay
├── translation.spec.ts             # Vérification texte traduit
├── visual-regression.spec.ts       # Régression visuelle (screenshots)
├── specs/
│   ├── menu-navigation.spec.ts     # Navigation menus
│   ├── dialogue-npc.spec.ts        # Dialogues NPC
│   ├── battle-flow.spec.ts         # Flux de combat
│   ├── exploration.spec.ts         # Exploration carte
│   └── reporter-smoke.spec.ts      # Smoke test du reporter
├── fixtures/
│   ├── emulator-fixture.ts         # Fixture Playwright pour l'émulateur
│   └── emulator-client.ts          # Client API émulateur
├── helpers/
│   ├── assertions.ts               # Assertions custom
│   ├── charmap.ts                   # Décodage texte
│   ├── constants.ts                # Constantes partagées
│   └── scenarios.ts                # Exécution de scénarios
├── reporters/
│   ├── error-reporter.ts           # Reporter custom principal
│   ├── error-classifier.ts         # Classification des erreurs
│   ├── report-generator.ts         # Génération JSON/Markdown
│   └── ticket-creator.ts           # Création de tickets YAML
└── snapshots/                      # Screenshots de référence
```

### Projets Playwright

La config (`playwright.config.ts`) définit 9 projets indépendants :

| Projet | Fichier | Description |
|--------|---------|-------------|
| `boot` | `boot.spec.ts` | Démarrage ROM, chargement savestates |
| `gameplay` | `gameplay.spec.ts` | Scénarios de jeu |
| `translation` | `translation.spec.ts` | Vérification des textes traduits |
| `visual-regression` | `visual-regression.spec.ts` | Comparaison de screenshots |
| `menu-navigation` | `specs/menu-navigation.spec.ts` | Navigation dans les menus |
| `dialogue-npc` | `specs/dialogue-npc.spec.ts` | Dialogues PNJ |
| `battle-flow` | `specs/battle-flow.spec.ts` | Flux de combat |
| `exploration` | `specs/exploration.spec.ts` | Exploration de la carte |
| `reporter-smoke` | `specs/reporter-smoke.spec.ts` | Smoke test du reporter |

### Commandes

```bash
# Lancer tous les projets
make test-playwright
# ou
npx playwright test

# Lancer un projet spécifique
npx playwright test --project=boot
npx playwright test --project=menu-navigation

# Lancer un fichier spécifique
npx playwright test tests/e2e-playwright/boot.spec.ts

# Mode debug (navigateur visible + inspecteur)
npx playwright test --debug

# Mettre à jour les screenshots de référence
npx playwright test --update-snapshots
```

### Configuration clé

- **Timeout test** : 120 s
- **Timeout expect** : 30 s
- **Workers** : 1 en CI, 2 en local
- **Retries** : 1 en CI, 0 en local
- **Screenshots** : capturés automatiquement en cas d'échec
- **Traces** : enregistrées au premier retry
- **Viewport** : 480 x 320 (résolution GBA)
- **Serveur web** : démarré automatiquement (`emulator-web/src/server.ts` sur le port 3000)

---

## Système de tickets automatiques

Le reporter Playwright génère automatiquement des tickets pour chaque erreur détectée.

### Fonctionnement

1. **Détection** — Le reporter (`error-reporter.ts`) capture chaque test en échec
2. **Classification** — L'erreur est classifiée (`error-classifier.ts`) en catégorie et sévérité
3. **Rapport** — Un rapport JSON et Markdown est généré dans `test-results/reports/`
4. **Ticket** — Pour les erreurs `critical` et `major`, un fichier YAML est créé dans `tickets/`

### Catégories d'erreurs

| Catégorie | Sévérité | Description |
|-----------|----------|-------------|
| `CRASH` | critical | Crash, PC invalide, reboot, freeze |
| `WRONG_TEXT` | major | Texte incorrect affiché |
| `MISSING_TRANSLATION` | major | Texte anglais non traduit |
| `VISUAL_REGRESSION` | major | Régression visuelle détectée |
| `ENCODING_ERROR` | major | Caractère corrompu, erreur charmap |
| `OVERFLOW` | minor | Texte qui déborde de la zone d'affichage |
| `TIMEOUT` | minor | Dépassement de timeout |

### Lire les rapports

```bash
# Rapports générés dans :
test-results/reports/
├── error-report.json       # Rapport JSON structuré
├── error-report.md         # Rapport Markdown lisible
├── results.json            # Résultats Playwright bruts
└── index.html              # Rapport HTML interactif
```

### Gérer les tickets

```bash
# Lister tous les tickets ouverts
make tickets
# ou
python3 scripts/list_tickets.py

# Filtrer par statut
python3 scripts/list_tickets.py --status open
python3 scripts/list_tickets.py --status resolved

# Filtrer par sévérité
python3 scripts/list_tickets.py --severity critical

# Filtrer par catégorie
python3 scripts/list_tickets.py --category CRASH
python3 scripts/list_tickets.py --category WRONG_TEXT

# Sortie JSON
python3 scripts/list_tickets.py --json

# Résoudre un ticket
python3 scripts/resolve_ticket.py <ticket_id>
python3 scripts/resolve_ticket.py <ticket_id> -r "Corrigé dans le commit abc123"
```

Les tickets sont stockés dans `tickets/` au format YAML et contiennent :
- Titre, catégorie, sévérité
- Test source
- Contexte (ROM, frame, expected/actual, screenshot)
- Étapes de reproduction
- Suggestion de correction

---

## CI/CD — GitHub Actions

### Workflow principal (`ci.yml`)

Déclenché sur push et pull request vers `master`.

```
┌──────────────────────┐     ┌───────────────────────┐
│ python-tests-fast    │     │ charmap-sync          │
│ (toujours)           │     │ (toujours)            │
│ pytest rapide        │     │ sync_charmap.py --check│
└──────────────────────┘     └───────────┬───────────┘
                                         │
┌──────────────────────┐     ┌───────────┴───────────┐
│ python-tests-standard│     │ emulator-web-tests    │
│ (push master seul.)  │     │ (toujours)            │
│ pytest standard      │     │ vitest run            │
└──────────────────────┘     └───────────┬───────────┘
                                         │
                             ┌───────────┴───────────┐
                             │ playwright-tests      │
                             │ (après emulator-web   │
                             │  + charmap-sync)      │
                             │ npx playwright test   │
                             └───────────────────────┘
```

| Job | Déclencheur | Ce qu'il teste |
|-----|-------------|----------------|
| `python-tests-fast` | Toujours | Tests unitaires rapides (< 1 min) |
| `python-tests-standard` | Push master uniquement | Tests standard sans emulator/stress |
| `charmap-sync` | Toujours | Vérifie que la charmap TS est synchronisée |
| `emulator-web-tests` | Toujours | Vitest sur `emulator-web/` |
| `playwright-tests` | Après emulator-web + charmap-sync | Tests E2E Playwright complets |

Les résultats de test sont uploadés comme artefacts GitHub (JUnit XML, rapports Playwright).

### Workflow benchmarks (`benchmarks.yml`)

Déclenché **manuellement** (`workflow_dispatch`). Lance `pytest tests/benchmarks/ -v` et uploade les résultats.

Pour le déclencher : onglet Actions > Benchmarks > Run workflow.

---

## Troubleshooting

### Les tests Python sont skippés

```
SKIPPED [1] tests/conftest.py: GBA_TEST_ROM not set
```

**Cause** : la variable `GBA_TEST_ROM` n'est pas définie.

**Solution** :
```bash
export GBA_TEST_ROM=/chemin/vers/votre/rom.gba
```

### Les tests E2E Python nécessitent mGBA

```
SKIPPED [1] tests/conftest.py: mGBA not available
```

**Solution** : installer mGBA (`brew install mgba` sur macOS, `apt install mgba-sdl` sur Ubuntu).

### Playwright ne trouve pas le navigateur

```
Error: browserType.launch: Executable doesn't exist
```

**Solution** :
```bash
npx playwright install chromium
# ou avec les dépendances systèmes (CI) :
npx playwright install --with-deps chromium
```

### Le serveur émulateur ne démarre pas

```
Error: Timed out waiting for server
```

**Causes possibles** :
1. Port 3000 déjà occupé — libérer le port ou changer `EMULATOR_PORT`
2. Dépendances non installées — `cd emulator-web && npm install`
3. Erreur dans le code serveur — `cd emulator-web && npx tsx src/server.ts` pour voir les logs

### Drift charmap détecté

```
Charmap drift detected!
```

**Solution** :
```bash
make sync-charmap
```

### Comment lancer un seul test

```bash
# pytest — par nom
pytest tests/test_text_codec.py::test_decode_basic -v

# pytest — par marker
pytest tests/ -m "rom" -v

# Playwright — par projet
npx playwright test --project=boot

# Playwright — par fichier
npx playwright test tests/e2e-playwright/specs/menu-navigation.spec.ts

# Vitest — par fichier
cd emulator-web && npx vitest run tests/charmap.test.ts
```

### Comment diagnostiquer un test Playwright qui échoue

1. Relancer en mode debug :
   ```bash
   npx playwright test --project=<projet> --debug
   ```
2. Consulter la trace (générée au premier retry) :
   ```bash
   npx playwright show-trace test-results/screenshots/<test>/trace.zip
   ```
3. Lire le rapport HTML :
   ```bash
   npx playwright show-report test-results/reports
   ```
4. Vérifier les tickets auto-générés :
   ```bash
   make tickets
   ```
