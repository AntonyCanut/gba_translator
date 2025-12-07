# Guide de traduction assistée

- English quickstart
  - `make extract` — dump original text, split into 250-line chunks, copy into `fr_chunks/` if empty.
  - `make build-fr` — combine `fr_chunks/*` into `combined_fr.txt` then inject into `totranslate_fr.gba` using free-space relocation (falls back to append).
  - Use `.venv/bin/python3` if present; otherwise `python3` system is used.
  - Sensitive offsets are kept in-place (low ROM areas), long strings are relocated to free space starting after `0x220000`.
  - Keep gibberish and binary lines unchanged; consult `fr_chunks/doutes.txt` before editing.

- Ne jamais modifier les offsets ni l’ordre des lignes dans `fr_chunks/*`.
- Conserver les contrôles (`\n`, `\p`, `\l`, `{...}`) et limiter chaque segment affiché à 36 caractères max.
- Ne pas supprimer les espaces blancs sauf si la longueur reste identique.
- Remplacer **move** par **capacité** ; MT = **CT** ; Gym = **Arène** ; Gym Leader = **Champion d’Arène**.
- Traduire les villes et les noms de Pokémon en français officiel quand ils existent.
- Traduire les noms d’attaques avec leur appellation officielle des jeux Pokémon (ex: Thunderbolt → Tonnerre).
- Laisser inchangées les chaînes illisibles/binaire et les lignes déjà en place.
- Garder `\p` et `\l` aux mêmes emplacements autant que possible.
- Avant chaque session, consulter/mettre à jour `fr_chunks/doutes.txt` pour les traductions incertaines.
- Chaque fichier de chunk doit contenir exactement 250 lignes (ni plus ni moins).
