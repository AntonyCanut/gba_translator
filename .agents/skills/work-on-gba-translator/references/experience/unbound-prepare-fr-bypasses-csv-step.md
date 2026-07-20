---
name: unbound-prepare-fr-bypasses-csv-step
description: "gba_translator build-fr chain now uses `make prepare-fr` (combined_fr.txt → JSON directly), the CSV step from the skill doc is stale"
metadata:
  node_type: memory
  type: project
  originSessionId: a8916010-fcc2-47b1-9fc5-c98b6c2a8a69
---

`combined_fr.txt` a déménagé vers `languages/fr/combined_fr.txt` (commit e55afa4, registre
multi-langue). La chaîne `apply_combined_fr.py --extend` → `09_csv_to_json_v2.py` documentée
dans le skill `translating-unbound` suppose une CSV trilingue dans
`output/translation/*.csv` qui **n'existe plus** dans l'état courant du dépôt
(`gba_translator` branche `test/pr`) — le script échoue avec `CSV file not found`.

Le Makefile a une cible plus directe : `make prepare-fr` (target `scripts/prepare_fr_json.py`)
génère `output/translation/<date>_translation_ready.json` **directement** depuis
`languages/fr/combined_fr.txt` + l'extraction EN, sans passer par la CSV. `make build-fr`
en dépend implicitement (`$(FR_TRANSLATION)` = JSON le plus récent du dossier).

**Why:** éviter de perdre du temps à chercher une CSV manquante ou à relancer
`apply_combined_fr.py` qui plante. Le flux validé et qui marche est :
```
languages/fr/combined_fr.txt
  └─→ make prepare-fr   (régénère le JSON le plus récent)
        └─→ make build-fr
```

**How to apply:** pour toute correction de texte FR (offsets pointer-based, classe 1), éditer
`languages/fr/combined_fr.txt` (toujours bloc minuscule fin de fichier, dernière entrée
gagne), committer, puis lancer `make prepare-fr && make build-fr` (pas le chemin CSV). Vérifier
ensuite les octets décodés dans `output/roms/GenedRom-fr.gba` via `src.core.text_codec.TextDecoder.decode_pokemon`.
Voir aussi [[unbound-fr-build-lives-in-gba-translator]] et [[translating-unbound-skill]].
