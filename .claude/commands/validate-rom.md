---
description: Valide une ROM construite (pipeline complet ou validation byte-level ES)
---

Valide une ROM générée.

- `es` (défaut) : `make validate-es` — validation byte-level de `GenedRom-es.gba`
  contre `spanishrom.gba` via l'offset map.
- `pipeline` : `make pipeline` — verify-roms → extract → diff → build-es → validate-es.
- Pour la ROM FR : décris l'écart attendu et lance les specs Playwright pertinentes
  (`make test-playwright`) plutôt qu'une comparaison byte-level (la FR diverge de l'ES).

Reporte le taux de validation. Rappel : 100 % attendu ; tout écart inattendu =
investigation (cause racine, pas contournement).

$ARGUMENTS
