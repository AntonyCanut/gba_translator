---
name: unbound-zone-name-table-vs-worldmap-labels
description: "Region/Town-Map zone-name strings are separate from world-map labels — translating the label doesn't fix the in-game zone popup"
metadata:
  node_type: memory
  type: project
  originSessionId: 872a4159-b0ff-4585-abfc-055286af529c
---

Les noms de lieux Unbound vivent dans **deux familles d'octets distinctes** ; traduire l'une ne corrige PAS l'autre :

1. **Labels carte du monde** (région map screen) : table indexée à `0x72xxxx` / `0xB5xxxx` (ex. `0x721304` Trou Glacé, `0xB514E4` Dehara). Lus par index → lire l'octet à l'offset == ce qui s'affiche. Couverts par `test_location_names_fr.py` (B-52).
2. **Strings zone-name / pop-up / menu vol** : table de pointeurs `0x1FB3D80-0x1FB4700` + `0x1EAF8C0-0x1EAFE80` ciblant des strings en `0x1Exxxxx`/`0x1Fxxxxx` (et la banner table fly `0x78D7xx`). Lus par **pointeur**.

La table zone-name est massivement française MAIS gardait des restes anglais joignables par pointeur (P-29 "pas traduit") : Icy Hole `0x1f21738`, Polder Town `0x1f52a74`, Dehara City `0x1ef9640`+`0x78d717`, Pokémon Day Care `0x1ef7438`, Newmoon Island `0x1f4d8c4`, Fallshore City `0x1f04760`, + `Ville de Fallshore` relocalisé `0x17af16` (source `0x77389C`, raté par B-52 qui n'a fixé que `0x720E74`).

Fix (T-25, commits 157cfca+d809e9e) : ajouter ces offsets à `combined_fr.txt` (bloc minuscule, last-wins) → chaîne complète `apply_combined_fr.py --extend` → csv_to_json → `make build-fr`. Les FR plus longs (Trou Glacé, Bourg Polder, Île du Croissant `too_long`) sont relocalisés et **tous** leurs pointeurs repointés (vérifié).

DÉTECTION = la bonne méthode e2e : pour chaque forme anglaise, chercher les occurrences **standalone** (string décodée == forme exacte) **joignables par un pointeur live** (`rom.count(struct.pack("<I", off+0x08000000))>0`). Octets orphelins non joignables = OK. Voir `tests/e2e/test_location_names_e2e.py`. Le match exact évite les faux positifs (ex. `Cinder Volcano West` banner ≠ `Cinder Volcano`).

HORS PÉRIMÈTRE assumé (comme B-51) : la banner table fly `0x78D7xx` est quasi 100% anglaise (Bellin/Crater/Blizzard/Tehl Town, Cinder Volcano West) — "broader P-29 map-name work", pas P-29. Voir [[unbound-fr-toponym-canon]], [[combined-fr-duplicate-offsets-last-wins]], [[unbound-fr-build-lives-in-gba-translator]].
