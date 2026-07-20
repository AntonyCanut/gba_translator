---
name: unbound-f109-orphaned-branch-recovery
description: F-109 (sprite Selection) livré en jeu mais jamais mergé dans unbound — retrouvé via git log --all sur une branche worktree orpheline
metadata:
  node_type: memory
  type: project
  originSessionId: 26708e0a-a38b-496b-b447-185cdb5acbaf
---

Ticket F-110 (suite de F-109) dépendait du travail de F-109 ("Selection 40x104.bmp" localisé et patché, offset 0x00E985D8, outil `languages/fr/sprites.py`/`src/graphics/sprite_rom.py` étendu avec flag `compressed`). Le ticket F-109 affichait pourtant `status: pending` et aucun des fichiers (`languages/fr/sprites.py`, `scripts/insert_sprite.py`, etc.) n'existait dans le worktree fraîchement préparé pour F-110.

Cause : le travail existait bien, committé avec un message clair (`feat(fr): locate and patch the naming-keyboard Selection sprite (F-109)`), mais uniquement sur une branche `worktree/f-109-...` jamais rebasée/mergée dans `unbound` — visible seulement via `git log --all --oneline` (pas `git log` seul). Le merge-base avec `unbound` était 2 commits derrière la branche F-109, sans conflit de fichiers avec les commits `unbound` plus récents.

Fix : `git cherry-pick <hash-F-108> <hash-F-109>` directement dans le nouveau worktree (basé sur `unbound` à jour) plutôt que de refaire le travail. Cherry-pick propre, tests unitaires (`tests/unit/test_sprite_rom.py`, `test_sprite_bmp.py`) verts après coup.

**Pattern général** : si un ticket dépendant (`dependsOn`) affiche `status: pending` alors que sa description narrative affirme qu'il a réussi, ne pas assumer que le travail est perdu — `git log --all --oneline | grep -i <mot-clé>` avant de recommencer depuis zéro. Voir aussi [[singularity-parent-merge-orphaned-by-child-ticket]] (cas inverse : enfant mergé, parent orphelin) et [[unbound-fr-build-lives-in-gba-translator]].
