# Sous-agents Ollama — gba_translator

Sous-agents spécialistes que l'assistant peut déléguer. Les définitions complètes sont
partagées avec Claude dans [`.claude/agents/`](../../.claude/agents) ; on les réutilise
telles quelles.

| Agent | Outils | Quand déléguer |
|-------|--------|----------------|
| [`rom-analyzer`](../../.claude/agents/rom-analyzer.md) | lecture, grep, bash | Inspecter octets/pointeurs/padding/diff d'une ROM, sans modifier |
| [`translation-verifier`](../../.claude/agents/translation-verifier.md) | lecture, grep, bash | Auditer une traduction FR (orthographe, toponymes, glyphes, placeholders) |
| [`test-runner`](../../.claude/agents/test-runner.md) | lecture, grep, bash | Lancer les suites de tests et trier les échecs (cause racine) |

Règle commune : ces agents sont en **lecture seule**, ne committent pas, et rapportent
une conclusion factuelle à l'agent principal.
