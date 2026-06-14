---
description: Synchronise la charmap Python -> TypeScript et vérifie l'absence de divergence
---

Après toute modification de `src/core/text_codec.py` (table de caractères, alias,
control codes) :

1. Lance `make sync-charmap` pour régénérer la charmap côté émulateur web (TypeScript).
2. Lance `make sync-charmap-check` pour confirmer qu'aucune divergence ne subsiste
   (c'est ce que vérifie le job CI `charmap-sync`).
3. Stage les deux fichiers (Python + TypeScript généré) dans le même commit.

$ARGUMENTS
