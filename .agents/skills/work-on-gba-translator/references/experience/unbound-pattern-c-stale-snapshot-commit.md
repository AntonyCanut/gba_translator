---
name: unbound-pattern-c-stale-snapshot-commit
description: "Pattern C = commit préparé sur une copie plus vieille que HEAD reverte silencieusement les fixes concurrents (9ad0fee, dc84690f) ; HEAD avance SOUS le checkout partagé sans checkout des fichiers → diffs/suppressions fantômes ; défense = relire au moment d'éditer + relire le diff du commit + CRITICAL_LABELS"
metadata:
  node_type: memory
  type: project
  originSessionId: e517d8aa-3e1b-48b7-aca0-5459af43cefd
---

Sur `gba_translator` (branche unbound), des agents concurrents committent en continu et
l'orchestrateur fait avancer HEAD **sous le checkout partagé sans mettre à jour les
fichiers** : `git status` montre alors des modifications/suppressions *fantômes* (fichiers
ajoutés par les nouveaux commits absents de l'arbre → « D », anciennes valeurs → « M »).
Tout `git add` + commit dans cet état reverte les fixes intermédiaires.

Cas réels : `9ad0fee` (2026-06-21, « Yes→Oui ») a détruit 5 offsets dont 0x1F0F842
(couleur ceinture/bottes) ; `dc84690f` (2026-06-22, « cri Leveinard ») a re-cassé le
template Méga-Cuff 0x83008C (→ anglais en jeu) ET supprimé son test. Je me suis fait
piéger moi-même le 2026-07-02 (5c88719, reverté proprement) — le commit vérifié par
`git show --stat HEAD` montrait 7 fichiers au lieu de 4.

2026-07-08 (clôture #74) : variante sans commit — le checkout principal `gba_translator`
avait un état **staged** (`git status` → `MM`) vieux de ~15h (mtime `.git/index` 21:29 vs
`date` 12:12 le lendemain, aucun process actif) qui, s'il avait été commit, aurait
silencieusement reverté 3 fixes déjà shippés : #72 (panneaux Carte du monde, réintroduisant
les vieilles entrées à l'offset -1 bugué), #74 (suppression pure et simple de `0x1F4E4E2`),
et une régression partielle de #73 (`0x1f4e012` remis à la version longue déjà rejetée pour
overflow dans `3c21d5a`). Détecté en comparant `grep` sur le fichier de travail vs
`git show HEAD:<fichier>` (entrée présente dans HEAD, absente du disque). Résolu par
`git stash push -u` (pas de reset --hard, réversible) puis revérifié `grep` + décodage de la
ROM construite à l'offset vivant.

**Why:** entre la lecture du fichier et le commit, 15-30 min passent ; sur ce dépôt c'est
assez pour que HEAD ait bougé 2-3 fois.

**How to apply:**
1. Relire `combined_fr.txt` **au moment d'éditer** (jamais un buffer d'il y a 15 min).
2. Committer immédiatement, chemins précis, AVANT tout build.
3. **Relire le diff du commit** (`git show HEAD -- <fichier>`) : le moindre offset/fichier
   étranger = `git reset --soft HEAD~1`, `git checkout HEAD -- <fichiers clobbés>`, refaire.
4. Entrée déjà perdue une fois → l'ajouter à `CRITICAL_LABELS` dans
   `scripts/check_translation_integrity.py` (gate le pre-commit via la suite rapide).
Doc de référence : `gba_translator/docs/20_TRANSLATION_PRESERVATION.md` §7 ; gotcha 13 du
CLAUDE.md de gba_translator ; Pattern C du skill [[translating-unbound-skill]].
Voir aussi [[singularity-worktree-commit-early]], [[singularity-build-resets-worktree]].
