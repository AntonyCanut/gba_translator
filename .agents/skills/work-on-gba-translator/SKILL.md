---
name: work-on-gba-translator
description: Appliquer les règles de développement et la mémoire technique durable de gba_translator/Pokémon Unbound. Utiliser pour toute tâche dans ce dépôt, notamment avant de planifier, modifier, tester, déboguer ou relire le pipeline ROM, les traductions FR/IT/DE, l'encodage CFRU, les patchs binaires, l'émulateur mGBA ou le workflow Git.
---

# Travailler sur gba_translator

Charger seulement le contexte utile, mais ne jamais commencer une modification sans avoir
consulté les règles et mémoires pertinentes.

## Charger le contexte

1. Lire `references/claude/memory/MEMORY.md` pour le socle projet maintenu dans le dépôt.
2. Lire `references/experience/MEMORY.md` pour l'index des retours d'expérience Claude liés
   à Unbound.
3. Rechercher les mots-clés de la tâche dans les deux ensembles de mémoires, puis lire en
   entier chaque fichier correspondant :

   ```bash
   rg -n -i "<mot-cle>|<offset>|<composant>" \
     .agents/skills/work-on-gba-translator/references/{claude/memory,experience}
   ```

4. Lire `references/claude/rules/patterns/00_index.md`, puis les règles qui correspondent
   aux fichiers et comportements touchés.

## Router les règles

- Toute modification : lire `patterns/forbidden.md`, `patterns/git-workflow.md` et
  `patterns/early-commit.md`.
- Python ou architecture : lire `patterns/python.md`, `patterns/architecture.md` et, si
  nécessaire, `architecture/python-conventions.md` ou `architecture/overview.md`.
- Pipeline, scripts ou Makefile : lire `patterns/scripts-pipeline.md`.
- Texte, pointeurs, charmap ou ROM : lire `patterns/text-encoding.md`.
- Code partagé ou build multilingue : lire `patterns/multilang-regression.md`.
- Tests : lire `patterns/testing.md` ; lire `testing/overview.md` pour les conventions
  détaillées pytest, Vitest ou Playwright.
- Émulateur web ou mGBA : lire `electron/web-emulator.md`.
- Travail concurrent : lire `multitasking.md`.
- Consulter `references/claude/project-rules.md` lorsqu'une règle historique ou un détail
  non couvert par l'index est nécessaire.

## Appliquer avec discernement

- Traiter `AGENTS.md`, le ticket courant et les instructions d'orchestration comme les
  contraintes prioritaires.
- Traiter les mémoires comme des retours d'expérience à vérifier contre le code, le
  `Makefile` et les artefacts actuels ; elles peuvent décrire un état ancien.
- En cas de divergence entre une copie Claude et le dépôt actuel, confirmer le comportement
  dans le code ou par un test, puis suivre l'état actuel.
- Ne jamais éditer les copies sous `references/` pendant une tâche métier. Mettre à jour la
  source Claude et resynchroniser explicitement lors d'une future migration de contexte.
