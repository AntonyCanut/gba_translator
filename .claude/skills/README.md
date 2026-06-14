# Skills — gba_translator

Procédures réutilisables chargées par l'agent. **Ordre de découverte** :

1. **Plugins installés** (superpowers : `brainstorming`, `test-driven-development`,
   `systematic-debugging`, `verification-before-completion`…). Toujours les préférer
   pour les méta-tâches (réflexion, debug, TDD, vérification).
2. **Skills du projet** (ce dossier) — procédures spécifiques au pipeline ROM.
3. **Rédaction fraîche** — n'écrire une nouvelle procédure que si rien au-dessus ne
   couvre le besoin, et la déposer ici en `kebab-case/SKILL.md`.

## Skills du projet

| Skill | Quand l'utiliser |
|-------|------------------|
| [`build-fr-rom`](build-fr-rom/SKILL.md) | Construire et valider la ROM FR de bout en bout |

## Skills de processus (superpowers, vendorés)

| Skill | Quand l'utiliser |
|-------|------------------|
| [`brainstorming`](brainstorming/SKILL.md) | Avant toute nouvelle feature ou décision d'archi |
| [`writing-plans`](writing-plans/SKILL.md) | Après brainstorming, avant de coder |
| [`test-driven-development`](test-driven-development/SKILL.md) | Avant d'écrire du code d'implémentation |
| [`systematic-debugging`](systematic-debugging/SKILL.md) | Sur tout bug / test en échec, avant de proposer un fix |
| [`code-review`](code-review/SKILL.md) | Après une tâche, avant intégration |
| [`verification-before-completion`](verification-before-completion/SKILL.md) | Avant toute affirmation « terminé »/commit |
