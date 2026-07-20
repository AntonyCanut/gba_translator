---
name: singularity-stale-attempt-phantom-merge-failure
description: "orchestration_complete rebondit en boucle avec « uncommitted change » fantôme alors que le worktree est prouvé propre → vérifier le statut du ticket : le moteur a peut-être respawné une tentative qui a déjà complété"
metadata:
  node_type: memory
  type: project
  originSessionId: 64aaaf73-a7de-4c0f-a4ea-0b243a790741
---

Symptôme (ticket F-66, 2026-07-02) : `orchestration_complete` échoue en boucle avec
« finalizeWorktree: 1 uncommitted change(s): M output/roms/GenedRom-fr.gba » alors que le
worktree est **cryptographiquement propre** (`git hash-object` disque == index == HEAD,
`git diff-index HEAD` vide, watcher 200 ms n'observe jamais d'état sale pendant la tentative).

Cause réelle : après 2-3 rebonds, le moteur Singularity **relance le ticket comme nouvelle
tentative** (nouveau run, autre instance d'agent). La nouvelle tentative complète le
merge-back avec succès ; la session d'origine devient **stale** — le log
(`~/Library/Logs/singularity/singularity-main.log`) montre « Ignored stale event from old
attempt », et ses `orchestration_complete` continuent de rebondir avec le message
« uncommitted change » **trompeur** (l'état est celui d'une machine fermée, pas du disque).

Réflexe : quand un complete rebondit alors que `git status --porcelain` est vide,
1. NE PAS spiraler sur le nettoyage git (mtime racy, filemode, update-index… vérifier une
   fois suffit) ;
2. `orchestration_get_current_ticket` → si `status: done`, une autre tentative a fini le
   travail : vérifier que les commits sont dans la branche de base, puis S'ARRÊTER sans
   rappeler complete ;
3. sinon greper le log moteur pour `merge-back` + taskId pour voir quel run/chemin échoue
   vraiment.

Contexte aggravant : les tickets texte FR concurrents créent des conflits binaires ROM en
rafale (chaque rebuild = ~160 Ko de cascade de relocalisation) ; chaque résolution =
rebuild ~4 min pendant lequel la base avance encore. Voir [[singularity-worktree-commit-early]],
[[unbound-build-determinism-relocation-order]].
