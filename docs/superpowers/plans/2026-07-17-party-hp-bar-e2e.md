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

- [ ] Ajouter au scénario l’attente d’un compteur d’entrées visitées supérieur à un.
- [ ] Exécuter `npm run test:e2e:party-hp-bar` et constater l’échec attendu avec le probe fixe.
- [ ] Faire parcourir au probe les entrées du menu principal jusqu’à correspondance exacte avec le golden.
- [ ] Réexécuter le scénario et obtenir 100 % de réussite sans mettre à jour le golden.
- [ ] Exécuter `npx tsc -p tsconfig.playwright.json --noEmit`.
- [ ] Relire le diff et vérifier l’absence d’artefacts temporaires.
