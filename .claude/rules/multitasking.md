# Multitâche & exécution parallèle

Plusieurs tickets peuvent avancer en parallèle sur ce dépôt. Règles d'isolation.

## Isolation par worktree

- Chaque ticket travaille dans un **git worktree** dédié sous
  `.singularity-worktrees/<task-id>/`, sur une branche `worktree/<slug>`, créée depuis la
  branche de base courante (`unbound`).
- Un seul agent écrit dans un worktree donné. Ne jamais éditer le code d'un autre
  worktree ni la copie principale pendant qu'un ticket est en cours.
- Lecture possible partout ; **écriture/commit uniquement** dans le worktree fourni.

## Verrou de session & ports

- `.singularity-session.lock` à la racine du worktree matérialise la session active —
  ne pas le supprimer ni le partager entre tâches.
- Les tests émulateur (Vitest/Playwright/mGBA) ouvrent des **ports** : avant de lancer
  une suite, vérifier qu'aucun runner concurrent ne tourne sur le même projet (sinon
  collision de port, base de test corrompue, flakiness). Attendre sa fin ou décaler.
- Une seule sonde mGBA à la fois ; sessions courtes + savestates.

## Limite de concurrence sûre

- Sous-agents en lecture seule (exploration/analyse) : parallélisme large OK.
- Tâches qui **buildent une ROM** ou lancent l'émulateur : **sérialiser** (1 à la fois
  par projet) — elles partagent les artefacts `output/` et les ports.
- Intégration : rebase only, jamais de merge (voir `patterns/git-workflow.md`).
