# Test E2E de la barre de vie du menu Pokémon

## Objectif

Reproduire l’écran signalé dans l’issue #84 à partir de la sauvegarde fournie et empêcher toute régression visuelle du libellé « PV » ou du cap gauche de la barre de vie.

## Approches examinées

1. Étendre la fixture Playwright globale avec une option de sauvegarde. Cette solution serait réutilisable, mais élargirait inutilement l’API de test et modifierait le démarrage de toute la suite.
2. Piloter directement `MgbaBridgeClient` depuis un test Playwright ciblé. Le test peut isoler la ROM et la save dans un répertoire temporaire, puis capturer l’écran exact sans toucher aux fixtures globales.
3. Ajouter un script de probe hors Playwright. Cela reproduirait le problème, mais ne fournirait pas une régression E2E intégrée à la suite demandée.

L’approche 2 est retenue : elle est ciblée, déterministe et suit les scénarios E2E natifs déjà présents dans `tests/e2e-playwright/specs/`.

## Conception

- La save utilisateur est conservée dans `tests/fixtures/saves/party_hp_bar_fr.sav`.
- Le test copie `output/roms/GenedRom-fr.gba` et la save sous le même nom de base dans un répertoire temporaire. mGBA charge ainsi automatiquement la sauvegarde batterie sans pouvoir modifier la fixture versionnée.
- Le scénario passe l’écran titre, charge « Continuer », ouvre le menu principal puis le menu Pokémon.
- Après stabilisation, le framebuffer 240×160 est comparé à un golden dédié. Cette image couvre le libellé « PV » et les pixels du cap gauche de la barre de vie dans leur rendu réel.
- Le nettoyage arrête toujours mGBA et supprime le répertoire temporaire, y compris en cas d’échec.

## Critères de succès

- Le test échoue si le libellé ou le cap de barre diffère du rendu validé.
- La fixture `.sav` garde exactement le même hash avant et après le test.
- Le scénario ne déclenche jamais la commande de sauvegarde du jeu.
- Le test passe sur `GenedRom-fr.gba` corrigée et reste exécutable isolément via un projet Playwright dédié.
