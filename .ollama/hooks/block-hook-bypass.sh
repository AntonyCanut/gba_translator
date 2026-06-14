#!/bin/sh
# Ollama preCommand — délègue au garde-fou partagé (bloque contournement de hook git,
# merge non-rebase, écriture dans input/roms/). Voir .claude/hooks/.
exec sh "$(dirname "$0")/../../.claude/hooks/block-hook-bypass.sh" "$@"
