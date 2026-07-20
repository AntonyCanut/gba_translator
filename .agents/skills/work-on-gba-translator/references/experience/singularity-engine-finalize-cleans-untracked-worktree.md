---
name: singularity-engine-finalize-cleans-untracked-worktree
description: "Le moteur Singularity peut nettoyer les fichiers non-trackés ET committer dans le worktree d'un ticket EN COURS — les artefacts régénérés (CSV/JSON/ROM non commités) disparaissent ; défense = tout committer atomiquement, et ne jamais piper make dans tail"
metadata:
  node_type: memory
  type: project
  originSessionId: 4484465e-b33f-4ade-8924-3d23c30287ba
---

Constaté le 2026-07-06 (ticket B-182 / issue #12 « Et hop ! »). Cause racine : un
`orchestration_complete` qui rebondit (« MERGE FAILED ») fait dispatcher un **run de retry**
alors que le run d'origine tourne encore → deux agents vivants sur le même worktree
(voir [[singularity-duplicate-dispatch-same-ticket-race]]). Le run de retry, en « récupérant
le merge » (bloqué par un symlink non-tracké `output/differences`), a :
1. supprimé les fichiers non-trackés du worktree (CSV trilingue copiée, JSON `*_translation_ready.json` régénéré, symlinks) ;
2. restauré `output/roms/GenedRom-fr.gba` à la version de HEAD (écrasant la ROM fraîchement buildée non commitée du run d'origine) ;
3. commité dans la branche du worktree (`chore: ignore output/differences…` + commit de la ROM) et relancé ses propres builds.

Les `orchestration_complete` suivants du run d'origine rebondissent avec des « uncommitted
changes » FANTÔMES (instantanés périmés de la course), alors que le ticket passe `done` et
que la branche est déjà intégrée. Vérifier `orchestration_get_current_ticket` (status +
previousResult révèle l'autre run) et l'état réel de `unbound`, puis S'ARRÊTER — ne pas
re-spammer complete (voir [[singularity-stale-attempt-phantom-merge-failure]],
[[singularity-zombie-run-stale-complete]]).

Symptôme trompeur : la suite passe, puis un run ciblé du même test échoue avec l'ANCIEN texte —
la ROM sur disque a été revertée entre les deux (mtime récent + `git status` propre = fichier
restauré depuis HEAD, pas un échec de build).

**Défenses :**
- Faire la passe complète en UNE commande atomique : régénérer CSV/JSON → `make build-fr` →
  vérifier octets → `git add` + commit → re-vérifier depuis `git cat-file -p HEAD:<rom>`
  (le blob commité est insensible aux clobbers). Voir [[singularity-worktree-commit-early]],
  [[singularity-build-resets-worktree]].
- Ne JAMAIS lancer `make build-* 2>&1 | tail -N` en arrière-plan : le code de sortie devient
  celui de `tail` (0) et l'output est tronqué à N lignes — un make en échec passe pour un
  succès. Lancer sans pipe (le fichier de sortie du background garde tout).
- Symlinks d'artefacts (`output/extracted`, `output/differences`) : les supprimer dès la fin
  du build, avant tout commit/pull — un untracked dans le worktree bloque la finalisation du
  moteur et déclenche son nettoyage. Voir [[unbound-worktree-generic-build-artifact-reuse]].
