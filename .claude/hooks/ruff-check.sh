#!/bin/sh
# PostToolUse(Edit|Write) — lint ruff sur le fichier Python qui vient d'être édité.
# Non bloquant : signale les erreurs (code 2 -> feedback) mais laisse l'agent corriger.

input=$(cat)
path=$(printf '%s' "$input" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')

case "$path" in
  *.py) ;;
  *) exit 0 ;;
esac

command -v ruff >/dev/null 2>&1 || exit 0

if ! out=$(ruff check "$path" 2>&1); then
  echo "ruff a relevé des problèmes sur $path :" >&2
  echo "$out" >&2
  echo "Corrige-les avant de committer (le hook pre-commit les rejettera sinon)." >&2
  exit 2
fi
exit 0
