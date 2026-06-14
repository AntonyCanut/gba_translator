#!/bin/sh
# Ollama postEdit — délègue au lint ruff partagé sur le fichier Python édité.
exec sh "$(dirname "$0")/../../.claude/hooks/ruff-check.sh" "$@"
