# Protocole early-commit — anti-perte de travail

Deux patterns de perte documentés dans ce dépôt. Les deux sont évitables.

---

## Pattern A — Race worktree reset

**Symptôme** : un ticket concurrent fait `git reset --hard HEAD` ou `git clean -f` dans le
dépôt principal → vos éditions non commitées disparaissent. Confirmé sur `combined_fr.txt`
(réinitialisation R-01 "nettoyage git").

**Règle absolue : commiter dès le premier fichier édité.**

```
# Ordre d'opérations imposé pour toute session de traduction
1. git status              # vérifier l'état initial
2. éditer combined_fr.txt  # ou tout autre fichier source
3. git add combined_fr.txt # immédiatement
4. git commit -m "fix(fr): ..."  # AVANT de builder la ROM
5. make build-fr           # build maintenant protégé
```

Ne jamais faire : éditer → builder → commiter. Le build (20-40 min) est la fenêtre
pendant laquelle un reset concurrent peut frapper.

**Checkpoint d'urgence** (si vous avez déjà des changements non commités) :
```bash
bash scripts/checkpoint_wip.sh   # crée un stash de sauvegarde
```

---

## Pattern B — Race d'index partagé

**Symptôme** : un autre agent fait `git add combined_fr.txt output/roms/...` dans le dépôt
principal au même moment → votre `git commit` emporte SES fichiers stagés → votre commit
contient silencieusement une version ANCIENNE de `combined_fr.txt` (revert involontaire).
Vécu lors de R-09 (juin 2026) : les traductions Gym→Arène ont été annulées ainsi.

**Règle : vérifier le contenu après chaque commit.**

```bash
git show --stat --oneline HEAD   # affiche les fichiers du dernier commit
```

Si un fichier inattendu apparaît :
```bash
git reset HEAD~1                 # défaire le commit (changements gardés dans le working tree)
git add <vos-fichiers-seulement> # stager uniquement ce que VOUS avez changé
git commit -m "..."              # recommiter proprement
```

Le hook `verify-commit-content.sh` affiche automatiquement ce résumé après chaque `git commit`.

---

## Récupération après perte

Voir `scripts/recover_lost_work.sh` pour le guide interactif.

En bref :
```bash
git reflog --oneline | head -20  # trouver le SHA avant la perte
git stash list                   # voir les stashs sauvegardés
git diff <sha-perdu> HEAD        # voir ce qui a disparu
git checkout <sha-perdu> -- combined_fr.txt  # récupérer un fichier spécifique
```

---

## Résumé des règles

| Règle | Pourquoi |
|-------|----------|
| Commiter après CHAQUE édition de source (avant build) | Reset concurrent possible à tout moment |
| `git add <fichiers-précis>` jamais `git add -A` | Évite d'emporter les stagings d'un autre agent |
| `git show --stat HEAD` après chaque commit | Détecte la race d'index partagé |
| `git stash push -m 'wip-checkpoint'` en début de session | Protège l'état initial contre un reset |
