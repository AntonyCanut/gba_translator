---
name: unbound-door-forced-shut-ambiguity-fix
description: "\"La porte a été forcée\" (repaire Ombre) était ambigu — fixé en vérifiant le dialogue suivant avant d'adopter la reformulation suggérée par l'utilisateur (issue #36)"
metadata:
  node_type: memory
  type: project
  originSessionId: e566dbe7-d828-40ed-ad72-a0f3e7c7c6ee
---

L'issue #36 proposait de remplacer "La porte a été forcée et s'est refermée derrière
toi." (0x1F0B460, sortie du repaire Ombre) par un texte parlant d'un mur/paroi
effondré. En vérifiant le dialogue suivant au même endroit (0x1F0B48A: "La porte
est solidement scellée."), il s'avère que le jeu garde bien une porte, pas un mur —
adopter la proposition "paroi" aurait introduit une incohérence narrative.

**Why:** le vrai bug n'était pas le sujet (porte) mais la formulation: "a été forcée"
seul se lit comme "forcée pour OUVRIR", ce qui contredit "et s'est refermée" juste
après. Fix retenu: "La porte s'est refermée de force derrière toi." (cohérent avec
la version italienne "La porta è stata chiusa a forza alle tue spalle.").

**How to apply:** quand un utilisateur propose un texte de remplacement pour un
dialogue Unbound, toujours vérifier les dialogues adjacents/liés au même
objet/décor avant d'adopter tel quel — la proposition peut résoudre le style mais
casser la cohérence avec une autre ligne qui référence le même objet narratif.
Voir aussi [[translating-unbound-skill]] pour le protocole édition/build/vérification.
