#!/bin/bash
# recover_lost_work.sh — Guide de récupération après une perte de travail git.
# Affiche les stashs et le reflog récent avec des commandes copy-paste.
#
# Usage : bash scripts/recover_lost_work.sh [--checkout-sha <sha>]

set -e
cd "$(git rev-parse --show-toplevel)"

if [ "$1" = "--checkout-sha" ] && [ -n "$2" ]; then
  echo "[recover] Création d'une branche de récupération depuis $2..."
  git checkout -b "recover/$(date +%Y%m%d-%H%M%S)" "$2"
  echo "Branche créée. Vérifiez le contenu et cherry-pick ce dont vous avez besoin."
  exit 0
fi

echo "================================================"
echo " RÉCUPÉRATION DE TRAVAIL PERDU — gba_translator"
echo "================================================"
echo ""

echo "=== STASH LIST (récupérable directement) ==="
if git stash list 2>/dev/null | head -10 | grep -q .; then
  git stash list | head -10
  echo ""
  echo "  Pour voir le contenu : git stash show -p stash@{0}"
  echo "  Pour restaurer       : git stash pop"
  echo "  Pour restaurer (N)   : git stash apply stash@{N}"
else
  echo "  (aucun stash)"
fi

echo ""
echo "=== REFLOG — états récents (30 derniers) ==="
git reflog --oneline --date=relative | head -30
echo ""
echo "  Pour voir ce qui a changé : git diff <sha> HEAD"
echo "  Pour récupérer un fichier : git checkout <sha> -- combined_fr.txt"
echo "  Pour créer une branche de récupération :"
echo "    bash scripts/recover_lost_work.sh --checkout-sha <sha>"

echo ""
echo "=== COMMITS ORPHELINS éventuels (ORIG_HEAD) ==="
if git rev-parse ORIG_HEAD 2>/dev/null; then
  echo "ORIG_HEAD pointe sur :"
  git log --oneline ORIG_HEAD -3
  echo ""
  echo "  Pour voir ce qui a été perdu :"
  echo "    git diff ORIG_HEAD HEAD -- combined_fr.txt"
  echo "  Pour récupérer depuis ORIG_HEAD :"
  echo "    git checkout ORIG_HEAD -- combined_fr.txt"
else
  echo "  (pas de ORIG_HEAD)"
fi

echo ""
echo "=== ÉTAT ACTUEL ==="
git log --oneline -5
echo ""
git status --short
