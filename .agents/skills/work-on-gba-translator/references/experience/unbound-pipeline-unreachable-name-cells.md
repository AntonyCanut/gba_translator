---
name: unbound-pipeline-unreachable-name-cells
description: "Cellules de noms d'objets injoignables par le pipeline → patch_fixed_table_names.py ; vérifier par décodage charmap, jamais par scan ASCII"
metadata:
  node_type: memory
  type: project
  originSessionId: e6845f7f-9f9a-4efd-9c09-76c96c9084a8
---

Pour les noms d'objets Unbound (ex. "Berry Pouch" → « Sac à Baies »), deux pièges récurrents (régression x2) :

1. **Cellules centrées injoignables** : les slots de nom centrés (12 octets `0x00`=espaces + nom, ex. `0x3DEED8`, `0x87A0B0`) sont absents À LA FOIS du `*_translation_ready.json` ET de l'extraction espagnole. La passe `apply_inline_overrides_fr.py` les saute (`if not ref_entry`), et `09_csv_to_json` ne les émet pas → **aucune passe de texte ne les atteint**. Seul recours : `scripts/patch_fixed_table_names.py` (patch byte-exact post-build, idempotent, validé par cellule), comme Parcel→Colis (`0x879DFC`) et Package→Paquet (`0x879E80`).

2. **Débordement de slot sans pointeur** : noms pilotés par le JSON dans des slots compactés sans pointeur (`0x41670A`, `0x417DE1`, 11 o). Une traduction plus longue (« Pochette Baies » 14 o) → `too_long` → repli silencieux sur l'anglais. **Choisir une trad byte-exact** : « Sac à Baies » = 11 glyphes = même longueur que « Berry Pouch » → s'insère sans relocalisation ni pointeur, centrage préservé.

**Règle de vérif** : la ROM est encodée en charmap CFRU, PAS en ASCII. Un `grep`/scan d'octets de la chaîne ASCII « Berry Pouch » renvoie toujours 0 (faux négatif — l'erreur de la run précédente). Toujours **décoder avec la charmap** (`src/text/decoder.decode_string_simple`) aux offsets, et scanner avec `encode_string(s, terminate=False)`.

**Instance confirmée (2026-06-15) : "Town Map" → « Carte »** dans la liste des objets. Mêmes cellules centrées `0x3DEE28`/`0x87A000`, nom lu par le sac à **base+12** (`0x3DEE34`/`0x87A00C`). Les entrées étaient **commentées** dans `patch_fixed_table_names.py` sous une note FAUSSE « déjà traduit par le pipeline » → l'objet restait « Town Map ». Leçon : **ne jamais croire un commentaire « déjà géré » — décoder la ROM buildée à l'offset.** Réactivé (stride 26, comme Berry Pouch) + test `TestTownMapCells`. Preuve la plus forte : lire la cellule via le bus mémoire mGBA (`read_memory(0x08000000+off,8)`) sur la ROM tournante → octets `bd d5 e6 e8 d9 ff` = « Carte ». Le sac Unbound est un « Cube » dont la navigation menu est trop flaky pour scripter un screenshot fiable (bridge drops) ; la preuve octets/bus mémoire > screenshot.

Le build lit le DERNIER `*_translation_ready.json` par mtime ; `combined_fr.txt` (source de vérité) peut déjà être correct dans HEAD alors que le JSON/CSV traînent l'ancienne valeur — corriger les 3 couches. Voir [[unbound-fr-build-lives-in-gba-translator]], [[combined-fr-duplicate-offsets-last-wins]], [[gba-translator-token-pipeline-pitfalls]].
