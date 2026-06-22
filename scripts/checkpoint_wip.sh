#!/bin/bash
# checkpoint_wip.sh — Sauvegarde l'état courant avant un reset/opération risquée.
# Utiliser en début de session ou avant toute opération git destructive.
# Le stash est récupérable même après git reset --hard HEAD.
#
# Usage : bash scripts/checkpoint_wip.sh [message-optionnel]

set -e
cd "$(git rev-parse --show-toplevel)"

msg="${1:-wip-checkpoint}"

# Rien à sauvegarder si l'arbre est propre
if git diff --quiet HEAD 2>/dev/null && git diff --cached --quiet 2>/dev/null && \
   [ -z "$(git ls-files --others --exclude-standard 2>/dev/null)" ]; then
  echo "[checkpoint] Arbre propre — rien à sauvegarder."
  git log --oneline -1
  exit 0
fi

echo "[checkpoint] État courant :"
git status --short

# Créer un stash (inclut les non-suivis pour les scripts nouveaux)
stash_name="$msg-$(git log --oneline -1 --format='%h')"
git stash push --include-untracked -m "$stash_name"

echo ""
echo "[checkpoint] Stash créé : $stash_name"
echo ""
echo "Pour récupérer : git stash pop"
echo "Pour voir : git stash show -p stash@{0}"
echo ""
echo "Stashs disponibles :"
git stash list | head -5
