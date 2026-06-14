#!/bin/sh
# PreToolUse(Bash) — bloque toute tentative de contournement des hooks git
# et toute modification interdite des ROMs sources. Sortie code 2 = blocage.
#
# Lit le JSON de l'événement sur stdin ; on en extrait la commande.

input=$(cat)
cmd=$(printf '%s' "$input" | sed -n 's/.*"command"[[:space:]]*:[[:space:]]*"\(.*\)".*/\1/p')

# 1. Contournement de hooks git
case "$cmd" in
  *--no-verify*|*HUSKY=0*|*GIT_SKIP_HOOKS=1*|*"git commit -n"*|*--no-gpg-sign*)
    echo "BLOQUÉ : contournement de hook git interdit (voir rules/patterns/git-workflow.md)." >&2
    exit 2 ;;
esac

# 2. Merge non-rebase (historique linéaire only)
case "$cmd" in
  *"git merge"*|*"git pull"*)
    case "$cmd" in
      *--rebase*|*"git pull --rebase"*) : ;;
      *) echo "BLOQUÉ : utilise git rebase, pas merge/pull (historique linéaire)." >&2
         exit 2 ;;
    esac ;;
esac

# 3. Écriture dans les ROMs sources (lecture seule)
case "$cmd" in
  *"input/roms/"*)
    case "$cmd" in
      *" > input/roms/"*|*"rm "*input/roms/*|*"mv "*input/roms/*|*"cp "*" input/roms/"*|*">> input/roms/"*)
        echo "BLOQUÉ : input/roms/ est en lecture seule." >&2
        exit 2 ;;
    esac ;;
esac

exit 0
