#!/bin/sh
# Codex post_edit — délègue au lint ruff partagé sur le fichier Python édité.
exec sh "$(dirname "$0")/../../.claude/hooks/ruff-check.sh" "$@"
