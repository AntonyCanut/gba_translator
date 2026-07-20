---
name: unbound-battle-options-fixed-width-descriptions
description: "Options menu (name+description) strings are a fixed-width inline table at 0x1f4da6c-0x1f4e244, per-string budget = original EN encoded length — no relocation possible"
metadata:
  node_type: memory
  type: project
  originSessionId: f4b95ee7-8d72-4298-bf1d-4338d9045b3c
---

Le menu Options (Options générales/audio/combat) est une table de chaînes CONTIGUËS
sans indirection de pointeur relocalisable, dans `0x1f4da6c`..`0x1f4e244` (englishrom.gba
et *_fr.gba mêmes offsets). Chaque nom d'option et chaque description de valeur a un
budget fixe = longueur encodée (octets CFRU) du texte EN d'origine. Si la traduction FR
dépasse ce budget, l'injection est **silencieusement skippée** (`too_long: True` dans le
rapport `prepare_fr_json.py`) et le texte reste en ANGLAIS dans la ROM — pas d'erreur
visible, juste un fallback discret. Voir aussi [[unbound-trace-live-pointer-not-original-offset]],
[[unbound-nopointer-inplace-budget]].

**Comment vérifier le budget avant d'écrire une traduction** :
```python
from src.text.encoder import encoded_length
encoded_length(new_fr_text, terminate=False)  # doit être <= original_length du rapport JSON
```
Ou lire `output/translation/<date>_translation_ready.json` → champ `original_length` de
l'entrée à l'offset visé (`too_long: True` = a été skippé, resté en EN dans la ROM buildée).

**Mapping confirmé (issue #60, 2026-07-07)** — décoder l'EN à l'offset pour identifier
sans ambiguïté quelle description appartient à quelle option (les noms et les descriptions
sont dans des blocs séparés, l'ordre des descriptions ne suit pas visuellement l'ordre des
noms dans combined_fr.txt) :
- `0x1f4dd24` = nom option "Take Wild Item" → FR "Objet capture" (était "Objet sauvage", faux sens)
- `0x1f4e1eb` = description de "Objet capture" (budget 40o, EN "Put a caught Pokémon's item in the Cube.")
- `0x1f4e0c8` = description de la valeur "Partage Exp." de l'option "Gain d'Exp." (budget 34o,
  EN "All Pokémon in the party gain Exp.") — PAS la description de l'option elle-même
  (celle-ci est à `0x1f4e086`, budget générique, différente)
- `0x1f4e10c` = description de "Restr. obj." (budget 41o, EN "Rules for using items in Trainer battles.")

Fix appliqué : `Objet capture` / `Envoie l'objet de PKMN capturé au Cube.` (39o) /
`Toute l'équipe gagne de l'EXP.` (30o, raccourci vs proposition initiale "EXP. pour tous
les PKMN de l'équipe." qui faisait 36o pour un budget de 34o — silencieusement retombé
en anglais lors du premier build, détecté par décodage direct de la ROM buildée) /
`Règles pour les objets en combat.` (33o).
