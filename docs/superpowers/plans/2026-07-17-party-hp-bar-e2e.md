# Test E2E de la barre de vie du menu Pokémon — plan d’implémentation

> **Pour les agents :** appliquer `test-driven-development` puis `verification-before-completion` à chaque tâche.

**Objectif :** Vérifier dans mGBA, à partir de la save utilisateur, que « PV » ne tronque plus la barre de vie du menu Pokémon.

**Architecture :** Un spec Playwright démarre directement le pont mGBA avec une copie temporaire de la ROM et de la save. Il navigue jusqu’au menu Pokémon, compare le framebuffer à un golden et contrôle l’immuabilité de la fixture.

**Stack :** TypeScript ES2022, Playwright, mGBA, `MgbaBridgeClient`.

---

### Tâche 1 : Ajouter la régression E2E

**Fichiers :**

- Créer : `tests/e2e-playwright/specs/party-hp-bar-fr.spec.ts`
- Créer : `tests/e2e-playwright/helpers/party-hp-bar-probe.ts`
- Créer : `tests/e2e-playwright/playwright.party-hp-bar.config.ts`
- Créer : `tests/fixtures/saves/party_hp_bar_fr.sav`
- Modifier : `package.json`

- [x] Écrire le scénario qui prépare une copie temporaire ROM/save, charge la partie, ouvre Pokémon et capture l’écran.
- [x] Ajouter une assertion de snapshot nommée `party-hp-bar-fr.png` et une assertion du hash de la save.
- [x] Exécuter `npm run test:e2e:party-hp-bar` et constater l’échec attendu pour golden absent.

### Tâche 2 : Valider le rendu corrigé

**Fichiers :**

- Créer : `tests/e2e-playwright/snapshots/specs/party-hp-bar-fr.spec.ts-snapshots/party-hp-bar-fr.png`

- [x] Exécuter le test sans golden pour produire la capture de référence depuis la ROM corrigée.
- [x] Inspecter visuellement le golden : « PV » lisible et cap gauche de barre intact.
- [x] Réexécuter le test sans mise à jour et obtenir 100 % de réussite.

### Tâche 3 : Vérification finale

**Fichiers :**

- Relire tous les fichiers précédents.

- [x] Exécuter le contrôle TypeScript `npx tsc --noEmit`.
- [x] Exécuter les tests unitaires FR liés au patch graphique.
- [x] Vérifier le diff, l’absence d’artefacts temporaires et l’intégrité SHA-256 de la fixture.
- [ ] Commiter avec `test(e2e): vérifier la barre de vie avec une sauvegarde`.

### Tâche 4 : Retrouver l’écran par exploration des menus

**Fichiers :**

- Modifier : `tests/e2e-playwright/specs/party-hp-bar-fr.spec.ts`
- Modifier : `tests/e2e-playwright/helpers/party-hp-bar-probe.ts`

- [x] Ajouter au scénario l’attente d’un compteur d’entrées visitées supérieur à un.
- [x] Exécuter `npm run test:e2e:party-hp-bar` et constater l’échec attendu avec le probe fixe.
- [x] Faire parcourir au probe les entrées du menu principal jusqu’à correspondance exacte avec le golden.
- [x] Réexécuter le scénario et obtenir 100 % de réussite sans mettre à jour le golden.
- [x] Exécuter `npx tsc -p tsconfig.playwright.json --noEmit`.
- [x] Relire le diff et vérifier l’absence d’artefacts temporaires.

### Tâche 5 : Corriger la vraie barre tronquée (page Capacités)

Le rapporteur a précisé que le défaut est sur le **deuxième onglet du statut**,
pas dans le menu Pokémon. Conception :
`docs/superpowers/specs/2026-07-25-summary-hp-bar-caps-design.md`.

**Fichiers :**

- Modifier : `languages/fr/patches/hp_labels.py`
- Modifier : `tests/test_patch_hp_labels_fr.py`
- Créer : `scripts/regress_summary_hp_bar.py`
- Créer : `tests/e2e-playwright/helpers/summary-screen-regions.ts`
- Créer : `tests/e2e-playwright/helpers/summary-hp-bar-probe.ts`
- Créer : `tests/e2e-playwright/specs/summary-hp-bar.spec.ts`
- Créer : `tests/e2e-playwright/playwright.summary-hp-bar.config.ts`
- Modifier : `package.json`

- [x] Restaurer la planche anglaise du bloc `0x00E9B4B8` et redessiner « PV »
      en géométrie anglaise sans toucher aux caps.
- [x] Couvrir la parité avec l’art anglais par des tests unitaires, sur l’art
      généré et sur la ROM construite.
- [x] Reconstruire la ROM FR (`make build-fr`).
- [x] Piloter mGBA jusqu’à la page Capacités dans la ROM FR et la ROM anglaise
      et exiger une bande de barre identique au pixel près.
- [x] Ajouter le contrôle négatif : la même comparaison doit échouer sur une
      copie régressée à la planche espagnole.
- [x] Exécuter `npm run test:e2e:summary-hp-bar`, `npm run test:e2e:party-hp-bar`
      et `npx tsc -p tsconfig.playwright.json --noEmit`.

### Tâche 6 : Étendre la preuve aux ROMs allemande et italienne

Le ticket B-557 a porté le correctif DE/IT sans dupliquer la validation E2E.

**Fichiers :**

- Renommer : `specs/summary-hp-bar-fr.spec.ts` → `specs/summary-hp-bar.spec.ts`
- Modifier : `tests/e2e-playwright/helpers/summary-hp-bar-probe.ts`
- Modifier : `tests/e2e-playwright/helpers/summary-screen-regions.ts`

- [x] Vérifier que la sauvegarde du rapporteur se charge dans les trois builds
      (elles dérivent toutes de `englishrom.gba`).
- [x] Remplacer les attentes en nombre de frames par une attente de
      stabilisation du framebuffer — la ROM allemande échouait parce que le
      rappel de quête avalait le `START`.
- [x] Mesurer le bruit de fond du menu (horloge vivante) pour fixer le seuil de
      stabilité, et exiger deux intervalles calmes consécutifs.
- [x] Paramétrer le scénario sur FR/DE/IT, chacun avec son contrôle négatif.
- [x] Cinq exécutions consécutives vertes.

### Tâche 7 : Fusionner les deux scénarios en une seule suite

Le scénario du menu Pokémon (tâches 1 à 4) comparait tout l'écran à un golden
issu du build français. Il est devenu rouge au rebase : ce n'est pas une
régression de la barre, ce sont les **icônes de Pokémon qui s'animent**, donc
aucun golden plein écran de cette page ne peut être stable. Le probe cherchait
par ailleurs l'écran *jusqu'à* correspondance avec ce même golden — l'assertion
qui suivait ne pouvait donc jamais échouer.

Les deux écrans sont désormais couverts par une seule suite, sur le même
principe que la page Capacités : référence = ROM anglaise, et seules les bandes
de barre — des tuiles BG immobiles — sont comparées.

**Fichiers :**

- Renommer : `summary-hp-bar*` → `hp-bar*` (spec, probe, régions, config, snapshots)
- Supprimer : `specs/party-hp-bar-fr.spec.ts`, `helpers/party-hp-bar-probe.ts`,
  `playwright.party-hp-bar.config.ts` et son golden plein écran
- Modifier : `scripts/regress_summary_hp_bar.py`, `package.json`

- [x] Faire capturer au probe le menu Pokémon traversé en chemin.
- [x] Relever les six bandes de barre du menu Pokémon et vérifier qu'elles sont
      déjà identiques à l'anglais dans les trois builds.
- [x] Étendre le contrôle négatif : effacer aussi le cap gauche du menu Pokémon.
- [x] Remplacer `test:e2e:party-hp-bar` et `test:e2e:summary-hp-bar` par
      `test:e2e:hp-bar`.
- [x] Trois exécutions consécutives de `npm run test:e2e:hp-bar` vertes.
