# Test E2E de la barre de vie du menu Pokémon — plan d’implémentation

> **Pour les agents :** appliquer `test-driven-development` puis `verification-before-completion` à chaque tâche.

**Objectif :** Vérifier dans mGBA, à partir de la save utilisateur, que « PV » ne tronque plus la barre de vie du menu Pokémon.

**Architecture :** Un spec Playwright démarre directement le pont mGBA avec une copie temporaire de la ROM et de la save. Il navigue jusqu’au menu Pokémon, compare le framebuffer à un golden et contrôle l’immuabilité de la fixture.

**Stack :** TypeScript ES2022, Playwright, mGBA, `MgbaBridgeClient`.

---

### Tâche 1 : Ajouter la régression E2E

**Fichiers :**

- Créer : `tests/e2e-playwright/specs/party-hp-bar-fr.spec.ts`
- Créer : `tests/fixtures/saves/party_hp_bar_fr.sav`
- Modifier : `playwright.config.ts`

- [ ] Écrire le scénario qui prépare une copie temporaire ROM/save, charge la partie, ouvre Pokémon et capture l’écran.
- [ ] Ajouter une assertion de snapshot nommée `party-hp-bar-fr.png` et une assertion du hash de la save.
- [ ] Exécuter `npx playwright test --project=party-hp-bar-fr` et constater l’échec attendu pour golden absent.

### Tâche 2 : Valider le rendu corrigé

**Fichiers :**

- Créer : `tests/e2e-playwright/snapshots/specs/party-hp-bar-fr.spec.ts-snapshots/party-hp-bar-fr.png`

- [ ] Exécuter `npx playwright test --project=party-hp-bar-fr --update-snapshots` pour produire le golden depuis la ROM corrigée.
- [ ] Inspecter visuellement le golden : « PV » lisible et cap gauche de barre intact.
- [ ] Réexécuter le test sans mise à jour et obtenir 100 % de réussite.

### Tâche 3 : Vérification finale

**Fichiers :**

- Relire tous les fichiers précédents.

- [ ] Exécuter le contrôle TypeScript `npx tsc --noEmit`.
- [ ] Exécuter les tests unitaires FR liés au patch graphique.
- [ ] Vérifier le diff, l’absence d’artefacts temporaires et l’intégrité SHA-256 de la fixture.
- [ ] Commiter avec `test(e2e): vérifier la barre de vie avec une sauvegarde`.
