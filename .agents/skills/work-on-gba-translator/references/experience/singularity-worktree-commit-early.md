---
name: singularity-worktree-commit-early
description: "Deux patterns de perte dans gba_translator : reset concurrent (Pattern A) et race d'index partagé (Pattern B) — protections en place depuis 2026-06-22"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 872a4159-b0ff-4585-abfc-055286af529c
---

Deux patterns de perte documentés dans `gba_translator`, tous deux maintenant protégés.

## Pattern A — Reset worktree concurrent

**Vécu :** R-01 "nettoyage git" a lancé `git reset --hard` + `git clean` → éditions non commitées de `combined_fr.txt` + ROM disparues. Constaté via `git reflog` → `reset: moving to HEAD` + `git status` propre.

**Why :** le dépôt `gba_translator` est partagé entre agents parallèles ; une opération git globale d'un autre ticket peut toucher l'arbre de travail à n'importe quel moment.

**Protections mises en place (commit 4eafd78, 2026-06-22) :**
- Hook `block-hook-bypass.sh` (PreToolUse) : bloque `git reset --hard` quand le dépôt est sale + bloque `git clean -f` sur fichiers précieux
- `scripts/checkpoint_wip.sh` : crée un stash de sauvegarde en une commande
- Règle `rules/patterns/early-commit.md` : séquence edit→commit→build imposée

**How to apply :** commiter IMMÉDIATEMENT après la première édition d'un fichier source — avant `make build-fr`. Le build (20-40 min) est la fenêtre de vulnérabilité.

## Pattern B — Race d'index partagé

**Vécu :** R-09 (juin 2026) — Agent A fait `git add combined_fr.txt` juste avant que B fasse `git commit` → commit de B embarque la version d'A → revert silencieux des traductions Gym→Arène.

**Why :** plusieurs agents partagent le même `.git/index` dans le dépôt principal.

**Protections mises en place (commit 4eafd78, 2026-06-22) :**
- Hook `verify-commit-content.sh` (PostToolUse Bash) : affiche le contenu du commit après chaque `git commit` pour détecter les fichiers inattendus
- Règle dans `multitasking.md` : documenter et alerter

**How to apply :** (1) toujours `git add <chemins-précis>` (jamais `git add -A`) ; (2) après chaque commit, vérifier `git show --stat HEAD` — si un fichier inattendu apparaît, `git reset HEAD~1` et recommiter. Voir [[combined-fr-duplicate-offsets-last-wins]].

## Pattern C — Worktree dédié réinitialisé pendant un wait/idle

**Vécu (ticket 58554de0, e2e fixture date hardcodée) :** édité `tests/e2e/conftest.py` +
`tests/e2e/test_nodulithe_passive_fr.py` dans un worktree `.singularity-worktrees/<ticket-id>/`
**dédié** (pas le repo principal), puis attente (sleep arrière-plan + ScheduleWakeup)
qu'un process pytest concurrent du même projet (autre ticket, autre worktree) se termine
avant de lancer mes propres tests. Au réveil : fichier signalé « modifié par
l'utilisateur ou un linter » avec le contenu PRÉ-édition restauré, `git status` propre,
`git log` montrant des commits d'autres tickets entrés sur `test/pr` entre-temps. Aucune
commande git lancée par moi. `recover_lost_work.sh` n'a rien trouvé (pas de reflog/stash).

**Why :** même un worktree nominalement isolé par ticket peut être resynchronisé par la
couche d'orchestration (rebase sur la base branch déplacée) à un moment hors du contrôle
de l'agent ; un rebase silencieux sur du contenu non commité le perd sans laisser de trace
récupérable.

**How to apply :** dans CE projet (gba_translator) la règle « commit avant build » ne
suffit pas — généraliser à « commit avant TOUT wait/idle », y compris une attente d'un
process tiers ou un `ScheduleWakeup`. Séquence : édite → vérifie syntaxiquement → commit →
seulement ensuite attends/teste/`orchestration_pull`. Si du travail manque au réveil,
vérifier `git status`+`git log` tout de suite plutôt que de supposer que les edits ont
survécu.

## Pattern C bis — Confirmé une 2e fois (issue #35, whiteout messages)

**Vécu (ticket 0911ad71, 2026-07-06) :** run précédent a édité `combined_fr.txt` +
rebuild ROM + écrit `tests/test_whiteout_message_fr.py`, tout validé (tests unitaires
+ décodage ROM OK), puis a attendu la fin de la suite de tests complète en arrière-plan
AVANT de commiter. Au retour du run suivant : les 3 fichiers étaient toujours non commités
dans le worktree dédié, `orchestration_complete` avait échoué avec « 3 uncommitted change(s)
left in the worktree ». Contrairement à Pattern C, le contenu n'était PAS perdu ici — juste
jamais commité avant l'appel de complete. Récupération simple : `git add` + `git commit` +
`git rebase unbound` (aucun conflit, branche déjà à jour) + re-vérification tests.

**How to apply :** commiter DÈS que le travail est validé (tests unitaires + vérif ROM),
AVANT de lancer/attendre la suite de tests complète en arrière-plan — ne pas laisser
`orchestration_complete` être le premier moment où les fichiers touchent l'index.

## Récupération après perte

```bash
cd /Users/akc/Projects/Test/gba_translator
bash scripts/recover_lost_work.sh   # affiche stashs + reflog + commandes copy-paste
```
