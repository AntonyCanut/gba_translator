---
name: unbound-weak-armor-nodulithe-fix
description: Talent passif Weak Armor (Nodulithe/Roggenrola) restait en anglais — cellule fixe 0xA37069 absente de toute table de noms patchée
metadata:
  node_type: memory
  type: project
  originSessionId: da0061c3-fae3-47ba-87dd-a4d71535bd27
---

Le nom du talent passif **Weak Armor** (Nodulithe/Roggenrola) à `0xA37069`
(cellule fixe 17 octets, sans pointeur, stride 0x11) restait en anglais dans
la ROM FR construite. Absent de `combined_fr.txt` ET de tout patch de table
de noms fixes — ni la pipeline de traduction ni `patch_fixed_table_names.py`
ne le couvraient. Un rebuild propre reproduit le bug à coup sûr.

Fix : entrée `NAME_FIXES[0xA37069] = ("Weak Armor", "Armurouillée", 17)` dans
`gba_translator/scripts/patch_fixed_table_names.py` (déjà invoqué par
`make build-fr`). « Armurouillée » (12 car.) tient dans la cellule de 17 o.
Test couvert : `tests/e2e/test_nodulithe_passive_fr.py::TestNodulithePassiveName`
(déjà écrit sans xfail dans le commit `26a03c0` — pas besoin de retirer de marker).
Résolu dans le ticket B-103.

**Why:** Même classe de bug que Berry Pouch/Town Map/Hard Stone/TM Case —
cellules class-2 absentes de translation_ready.json ET de l'extraction
espagnole, donc invisibles à la pipeline de relocalisation/injection.
**How to apply:** Si un autre nom de talent/objet/Pokémon ressort en anglais
après un rebuild propre, chercher d'abord son offset par scan ROM puis
vérifier s'il existe une entrée `NAME_FIXES` correspondante — voir aussi
[[unbound-pipeline-unreachable-name-cells]].
