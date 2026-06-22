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

# 4. git reset --hard avec des changements non commités = perte garantie
#    Bloquer pour forcer un stash/commit préalable.
case "$cmd" in
  *"git reset"*"--hard"*)
    if git diff --quiet HEAD 2>/dev/null && git diff --cached --quiet 2>/dev/null; then
      : # arbre propre, reset autorisé
    else
      echo "BLOQUÉ : git reset --hard avec des changements non commités (perte garantie)." >&2
      echo "Sauvegarder d'abord :" >&2
      echo "  git stash push -m 'wip-checkpoint'   # stash récupérable après reset" >&2
      echo "  ou : git add <fichiers> && git commit -m 'wip: checkpoint'" >&2
      echo "Puis relancer le reset." >&2
      exit 2
    fi ;;
esac

# 5. git clean -f/-fd avec des fichiers non suivis potentiellement précieux
#    (hors output/ qui est gitignored et reproductible)
case "$cmd" in
  *"git clean"*"-f"*)
    untracked=$(git ls-files --others --exclude-standard 2>/dev/null | grep -v "^output/" | head -5)
    if [ -n "$untracked" ]; then
      echo "BLOQUÉ : git clean va supprimer des fichiers non suivis précieux :" >&2
      echo "$untracked" >&2
      echo "Ajouter ces fichiers au commit d'abord, ou vérifier que leur perte est intentionnelle." >&2
      echo "Pour autoriser : git stash --include-untracked puis git clean -f" >&2
      exit 2
    fi ;;
esac

exit 0
