# Configuration Ollama — gba_translator

Configuration de l'assistant local (Ollama) pour ce dépôt de traduction de ROMs GBA.
Les **règles de code** sont mutualisées avec Claude : voir
[`.claude/rules/patterns/`](../.claude/rules/patterns/00_index.md) et
[`.claude/project-rules.md`](../.claude/project-rules.md). Ce dossier ne fait que les
**câbler** pour Ollama et activer ses capacités.

## Fichiers
- [`Modelfile`](Modelfile) — modèle + prompt système (charge les conventions du projet).
- [`config.json`](config.json) — câblage des capacités (multitâche, sous-agents, MCP,
  hooks, skills, slash commands), en réutilisant les assets partagés.
- [`agents/`](agents/README.md) — sous-agents spécialistes.
- [`commands/`](commands/README.md) — slash commands.
- [`hooks/`](hooks/) — hooks de cycle de vie (délèguent aux scripts partagés).
- [`skills/`](skills/README.md) — procédures réutilisables.
- [`mcp.json`](mcp.json) — serveurs MCP exposés.

## Build du modèle
```bash
ollama create gba-translator -f .ollama/Modelfile
ollama run gba-translator
```
