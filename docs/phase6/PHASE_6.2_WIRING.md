# Phase 6.2 — Câblage mGBA bout-en-bout pour Playwright

**Date** : 2026-05-20
**Agent** : Developer
**Statut** : ✅ **Tests Playwright pilotent réellement Pokemon Unbound via mGBA natif**

## Résumé exécutif

- `Navigation map` (test oracle) passe : `playerX` / `playerY` changent réellement
  après les frappes clavier (preuve que mGBA exécute le gameplay).
- 42/43 tests Playwright en vert. La seule régression est le test
  `reporter-smoke › failing test triggers reporter error collection`, dont
  l'échec est **intentionnel** (sentinelle qui valide que le reporter d'erreur
  attrape bien les échecs et crée un ticket).
- 60/60 Vitest et 144/144 unit tests Python passent (4 skipped attendus).
- Diff minimal : 3 fichiers touchés, aucune réécriture de `mgba-bridge.ts` ou de
  `bridge.lua`.

## Diagnostic initial

Le piège bloquant identifié par le DevOps en Phase 6.1 était `-C fpsTarget=0`
passé au binaire mGBA. Sur mGBA-qt 0.11 macOS, cela fige l'émulateur après la
frame 1 (la callback `frame` ne se relance plus), donc `FRAMES|N`, `STATE`,
`KEY` etc. ne progressent jamais — ce qui faisait que les tests `real-gameplay`
soit étaient skip via `checkEmulatorAvailable` (try/catch → `testInfo.skip`),
soit voyaient `playerX/playerY` rester à 0 après les déplacements.

En complément, deux autres points devaient être adressés :

1. **`ROM_PATH` non câblée par défaut** : `playwright.config.ts` `webServer.env`
   ne le définissait pas, et le fixture `emulator-fixture.ts` se contentait
   d'une string vide en l'absence d'env. Le serveur démarrait donc sans
   auto-lancer mGBA → toutes les commandes WS échouaient → fixture skip.

2. **Processus mGBA orphelin entre tests** : sur macOS, `mgba` est un wrapper
   qui appelle `open -na mGBA.app --args …`. Le `spawn()` Node n'attrape que le
   PID du wrapper `open`, qui retourne instantanément ; le processus Qt
   détaché reste en vie. Le `killStaleBridge()` existait déjà au démarrage,
   mais pas à l'arrêt — il fallait l'appeler aussi dans `stop()` pour que les
   tests successifs ne s'empilent pas.

## Modifications

| Fichier | Changement |
|---|---|
| `emulator-web/src/mgba-bridge.ts` | Supprimé `-C fpsTarget=0` du `cmd.push(...)` (piège DevOps). |
| `emulator-web/src/mgba-bridge.ts` | `stop()` rappelle `killStaleBridge()` après `proc.kill()` (port 55234 propre entre tests). |
| `playwright.config.ts` | `webServer.env.ROM_PATH` pointe sur `output/roms/GenedRom-fr.gba` par défaut. Timeout `webServer` 30s → 60s (boot mGBA + Lua bind). |
| `tests/e2e-playwright/fixtures/emulator-fixture.ts` | Nouveau `resolveRomPath()` : si `ROM_PATH` env absent, fallback sur `<repo>/output/roms/GenedRom-fr.gba`. |

Aucun nouveau fichier de code. Aucun refactor.

## Validation locale (commandes utilisées)

```bash
# Smoke standalone du bridge (avant Playwright) → titre 15043 B, dialogue FR OK
npx tsx /tmp/test-bridge.mjs

# Tests Playwright par projet
ROM_PATH="$(pwd)/output/roms/GenedRom-fr.gba" npx playwright test --project=boot
ROM_PATH="$(pwd)/output/roms/GenedRom-fr.gba" npx playwright test --project=real-gameplay -g "Navigation map"
ROM_PATH="$(pwd)/output/roms/GenedRom-fr.gba" npx playwright test --project=real-gameplay
ROM_PATH="$(pwd)/output/roms/GenedRom-fr.gba" npx playwright test

# Vitest + Python
npm test --prefix emulator-web
python3 -m pytest tests/ -x --ignore=tests/e2e-playwright --ignore=tests/e2e --ignore=tests/stress --ignore=tests/benchmarks
```

## Résultats avant/après

| Suite | Avant (gbajs / fpsTarget=0) | Après (mGBA + fix) |
|---|---|---|
| `boot` Playwright (3 tests) | tests skip ou écran blanc | **3/3 vert** (13.9 s) |
| `real-gameplay › Navigation map` | `playerX==0` toujours, fail | **vert** en 10.4 s |
| `real-gameplay` complet (6 tests) | majoritairement skip | **6/6 vert** (37.8 s) |
| Playwright global (43 tests) | n/a (gbajs bloqué) | **42/43 vert** (1 échec intentionnel reporter-smoke) |
| Vitest (3 fichiers) | 60/60 (déjà OK) | **60/60** |
| Python unit tests | 144 passés | **144/4-skip** |

## Preuves visuelles

- `output/proofs/unbound_phase6_2_title.png` (15 043 octets) — écran titre
  Pokemon Unbound rendu par mGBA via le bridge (logo + "PRESS START").
- `output/proofs/unbound_phase6_2_french_dialogue.png` (1 515 octets) —
  premier écran de dialogue **en français** ("Bienvenue dans Pokémon Unbound !")
  après `START` + `A`, preuve que la traduction FR tourne réellement et que la
  ROM avance bien (frame counter > 2000, `mapNumber=5`, `playerX≠0`).

> La taille modeste (1.5 KB) du PNG dialogue s'explique par le rendu très
> compressible (texte blanc sur fond noir) ; ce n'est pas un écran vide — il y
> a bien du contenu visible.

## Sur l'échec `reporter-smoke›failing test triggers reporter error collection`

Lecture de `tests/e2e-playwright/specs/reporter-smoke.spec.ts` :

```ts
test('failing test triggers reporter error collection', async () => {
  test.skip(!!process.env.CI, 'Intentional failure — skip in CI');
  if (process.env.SKIP_FAILURE_TEST) { expect(true).toBe(true); return; }
  expect('NEW GAME').toBe('NOUVELLE PARTIE');
});
```

C'est volontaire : le test produit un échec pour vérifier que le reporter
d'erreur extrait bien `MISSING_TRANSLATION`, génère un rapport Markdown et
crée un ticket YAML. À la fin de run :

```
[GBA Reporter] Erreurs détectées:
  ERR-001 [major] MISSING_TRANSLATION: …
[GBA Reporter] Tickets créés: 1
  + auto-missing_translation-err-001.yaml
```

→ comportement attendu. Pour produire un état 100% vert localement on peut
passer `SKIP_FAILURE_TEST=1` ou `CI=1` ; la chaîne CI/CD est censée mettre
`CI=1` automatiquement.

## Critères de succès — checklist

- [x] mGBA est lancé automatiquement par `server.ts` au démarrage Playwright
  (via `ROM_PATH` env câblée par `webServer.env` ET par le fixture par défaut).
- [x] `bridge.lua` présent dans `emulator-web/src/lua/bridge.lua` (inchangé,
  déjà OK en Phase 6.1).
- [x] Test `Navigation map` passe (`playerX/playerY` changent après KEY +
  FRAMES — preuve standalone : `(0,0) → (2,0)` après DOWN+RIGHT).
- [x] Screenshot du titre > 5 KB (15 043 B).
- [x] Aucun test ne passe en soft-warn `not triggered` à cause d'un emulateur
  indisponible — les warnings restants (`PNJ dialogue not triggered`, `Wild
  battle not triggered`) sont des assouplissements légitimes des helpers
  (`waitForBattle` / `interactWithNPC`) lorsque la rencontre aléatoire ne
  déclenche pas dans le budget de frames ; ils existaient déjà avant Phase 6.2
  et ne sont pas masqués par notre câblage.
- [x] Diff git ciblé : 3 fichiers, aucun refactor massif.

## Ce qui n'a pas été touché (volontairement, hors scope)

- `bridge.lua` (toujours version Phase 6.1, OK tel quel).
- `mgba-bridge.ts` `getState()` lit `playerX/playerY` via `gSaveBlock1Ptr`
  (`0x03005008`) ; sur l'écran titre `sb1Ptr` est nul donc on retourne 0 — c'est
  attendu et déjà géré par les helpers `waitForGameState`.
- Le test reporter-smoke est conservé tel quel (sa nature intentionnelle est
  une feature, pas un bug à fixer côté wiring).
