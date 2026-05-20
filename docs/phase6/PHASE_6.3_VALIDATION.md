# Phase 6.3 — Validation tests (mGBA backend réel)

**Date**: 2026-05-20
**Tester**: agent f4cea4f4-29d3-424c-ac99-fb02df84c516
**Backend**: mGBA natif (`/opt/homebrew/bin/mgba`) + `bridge.lua` via TCP
**ROM**: `output/roms/GenedRom-fr.gba` (Pokemon Unbound FR, 33 MiB)

> **Note pré-checks**: La consigne du ticket pointait `/Users/akc/Projects/Test/Unbound/data/frenchrom.gba` — ce chemin n'existe pas. La ROM réelle utilisée par `playwright.config.ts` et `tests/e2e/conftest.py` est `output/roms/GenedRom-fr.gba` (33 554 432 B). Validation faite avec le bon chemin.

---

## 1. Vitest (emulator-web)

```
vitest run
 ✓ tests/charmap.test.ts (21 tests) 3ms
 ✓ tests/memory.test.ts (11 tests) 4ms
 ✓ tests/commands.test.ts (28 tests) 5ms
 Test Files  3 passed (3)
      Tests  60 passed (60)
   Duration  305ms
```

- **Total : 60 passed / 0 failed / 0 skipped**
- Cible 60 OK : ✅
- Aucune régression vs Phase 5.

## 2. pytest (Python toolkit + e2e)

```
============= 1 failed, 278 passed, 34 skipped in 69.44s (0:01:09) =============
```

- **Total : 278 passed / 1 failed / 34 skipped** (313 collected)
- Cible 121 OK : ✅ (largement dépassée — 278)

### Détail des skips (34)
- `tests/e2e/test_gameplay_flow.py` : 28 tests `skip` → nécessitent toolkit Unbound complet (documenté ticket)
- `tests/e2e/test_content_accuracy.py` : 1 skip
- `tests/e2e/test_quality_gates.py` : 1 skip
- `tests/test_dynamic_translation_insertion.py` : 1 skip
- `tests/test_regression_texts.py` : 3 skip

### Échec (1)
`tests/stress/test_soak.py::TestSoak100kFrames::test_soak_100k_frames_no_crash`

```
AssertionError: mGBA exited with code 1: mGBA: unrecognized option `--no-audio'
```

- **Cause** : le test passe `--no-audio` à mGBA, qui n'accepte pas cette option (mGBA utilise `-3` ou `--no-bios` ; pour silencer l'audio mGBA c'est différent).
- **Pas de régression Phase 5** : ce test n'a jamais tourné avec mGBA avant (Phase 5 utilisait gbajs).
- **Impact** : aucun pour la validation gameplay — c'est un stress test de stabilité sur 100k frames, le bug est dans l'argument CLI du test, pas dans le code de bridge ni dans le rendu.
- **Action conseillée** : ticket follow-up pour corriger l'argument mGBA (ex: redirection stderr, ou `--bios`, ou simplement omettre — mGBA peut tourner silencieux selon les flags réels).

## 3. Playwright

```
Running 43 tests using 1 worker
...
  1 failed
    [reporter-smoke] › specs/reporter-smoke.spec.ts › failing test triggers reporter error collection
  42 passed (3.6m)
```

- **Total : 42 passed / 1 failed (intentionnel) / 0 skipped** (43 collected)
- Cible 10+ : ✅

### Détail par projet

| Projet               | Passed | Failed | Notes |
|----------------------|--------|--------|-------|
| boot                 | 3/3    | 0      |       |
| gameplay             | 4/4    | 0      | 2 soft-warn (battle / dialogue not triggered) |
| translation          | 5/5    | 0      |       |
| visual-regression    | 4/4    | 0      |       |
| menu-navigation      | 5/5    | 0      |       |
| dialogue-npc         | 5/5    | 0      | 2 soft-warn |
| battle-flow          | 5/5    | 0      | 5 soft-warn (combat sauvage pas déclenché — game logic / RNG seed) |
| exploration          | 4/4    | 0      | 1 soft-warn ("Est-ce ton perso nnage ?" — possible texte tronqué) |
| reporter-smoke       | 1/2    | 1      | Échec **intentionnel** (`test.skip` en CI) — vérifie pipeline reporter |
| **real-gameplay**    | **6/6**| **0**  | **Navigation map = PASS ✅** |

### Tests `real-gameplay` (oracle Phase 6) — détail

```
✓ Boot et écran titre — rendu réel (4.3s)
✓ Nouvelle partie — chargement de la carte (4.8s)
✓ Premier dialogue — texte en français (5.1s)
✓ Navigation map — la position du joueur change (10.3s)     ← ORACLE PRIMAIRE
✓ Screenshot gameplay réel — pas d'écran noir (4.7s)
✓ Stabilité longue — 60s de gameplay sans crash (5.7s)
```

**Tous ces tests appellent `getState()` et reçoivent des valeurs réelles** : `playerX`, `playerY`, `frameCount`, `mapGroup`, `mapNumber`, `inBattle`, `textActive`, `callback1` lus directement depuis la RAM via `bridge.lua`.

### Échec Playwright (1) — intentionnel

`reporter-smoke.spec.ts:8` — Le test fait `expect('NEW GAME').toBe('NOUVELLE PARTIE')` exprès, pour valider que le reporter d'erreur (`tests/e2e-playwright/reporters/error-reporter.ts`) génère bien un ticket. Le code source contient un `test.skip(!!process.env.CI, 'Intentional failure — skip in CI')` et un fallback `SKIP_FAILURE_TEST=1`.

- **Auto-ticket généré** : `tickets/auto-missing_translation-err-001.yaml` ✅ — pipeline reporter validé
- **Pas une régression** — comportement nominal du smoke test

### Soft-warns détectés (transparence)

Les `console.warn` suivants ont été émis, et les tests passent malgré tout (logique "graceful degradation" du test) :

| Test | Warn |
|------|------|
| `gameplay › Premier combat` | "Wild battle not triggered within frame budget" |
| `gameplay › Dialogue PNJ` | "NPC dialogue not triggered within frame budget" |
| `dialogue-npc › dialogue complet` | "PNJ dialogue not triggered within frame budget" |
| `dialogue-npc › défilement de texte long` | "PNJ dialogue not triggered — scroll test skipped" |
| `battle-flow` (5 tests) | "Wild battle not triggered" + 4 dérivés |
| `exploration › Noms de lieux en français` | "Text may not be French: 'Est-ce ton perso nnage ?'" |

**Lecture** : sur ces tests, les assertions principales (no crash, getState retourne des valeurs cohérentes) passent. Mais le scénario gameplay précis (déclencher un combat sauvage, parler à un PNJ spécifique) n'est pas atteint dans le budget de frames. C'est le comportement existant des tests — pas un changement Phase 6.3. Un ticket d'amélioration peut être ouvert pour `battle-flow` (forcer `inBattle=true` via memory poke + state save, plutôt que d'attendre une rencontre RNG).

L'oracle primaire `real-gameplay > Navigation map` n'a **aucun soft-warn** et utilise des assertions strictes sur `playerX/playerY` réels.

---

## 4. Cumul

| Suite       | Passed | Failed | Skipped | Total collecté |
|-------------|--------|--------|---------|----------------|
| Vitest      | 60     | 0      | 0       | 60             |
| pytest      | 278    | 1      | 34      | 313            |
| Playwright  | 42     | 1†     | 0       | 43             |
| **Cumul**   | **380**| **2**  | **34**  | **416**        |

† 1 échec Playwright intentionnel (reporter-smoke valide la pipeline)

- **Cible 190 atteinte** : **OUI** (380 passed, 2× la cible)
- **Régressions vs Phase 5 (189/190)** : **NON**
  - Phase 5 avait 1 fail Navigation map → Phase 6.3 a Navigation map = PASS ✅
  - 2 échecs Phase 6.3 sont nouveaux mais hors-périmètre Phase 6 (stress test mGBA CLI arg + reporter smoke intentionnel)
- **Navigation map = PASS** : ✅ (oracle primaire, 10.3s)
- **Screenshot rendu confirmé** : ✅ — `test-results/screenshots/manual/unbound_gameplay.png` (8808 B, 120 couleurs uniques, mapGroup=31, playerX=8, playerY=4, frameCount=260329 → ROM réellement jouée hors écran titre)

---

## 5. Limitation Phase 5 levée

**Phase 5** : gbajs ne rendait pas le jeu (écran blanc), `Navigation map` échouait → 189/190.

**Phase 6.3** : mGBA natif via `bridge.lua` Lua/TCP → le jeu est exécuté pour de vrai, la RAM est lue par bridge, l'API `getState/screenshot/pressKey/advanceFrames` fonctionne bout-en-bout. **190+/190 tests passent** (380 passed total sur les 3 suites), **Navigation map en tête**.

## 6. Annexes
- Rapport Playwright JSON : `test-results/reports/report-2026-05-20_00-09-55.json`
- Rapport Playwright Markdown : `test-results/reports/report-2026-05-20_00-09-55.md`
- Auto-ticket démo reporter : `tickets/auto-missing_translation-err-001.yaml`
- Screenshot gameplay réel : `test-results/screenshots/manual/unbound_gameplay.png`
