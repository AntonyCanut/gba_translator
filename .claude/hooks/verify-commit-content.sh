#!/bin/sh
# PostToolUse(Bash) — après git commit, affiche le contenu committé.
# Détecte la race d'index partagé : si des fichiers inattendus apparaissent,
# l'agent peut annuler le commit (git reset HEAD~1) et recommiter proprement.
#
# Sortie code 2 = feedback affiché à l'agent (non bloquant).

input=$(cat)
cmd=$(printf '%s' "$input" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p')

case "$cmd" in
  *"git commit"*)
    echo "" >&2
    echo "=== [INDEX-RACE GUARD] Fichiers inclus dans ce commit ===" >&2
    git show --stat --oneline HEAD 2>/dev/null >&2
    echo "" >&2
    echo "Si des fichiers INATTENDUS apparaissent ci-dessus (race d'index partagé) :" >&2
    echo "  git reset HEAD~1           # défait le commit, garde les changements" >&2
    echo "  git add <vos-fichiers>     # stager uniquement vos fichiers" >&2
    echo "  git commit -m '...'        # recommiter proprement" >&2
    exit 2 ;;
esac

exit 0
