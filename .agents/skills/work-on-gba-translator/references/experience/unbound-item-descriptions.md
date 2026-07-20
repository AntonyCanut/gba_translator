---
name: unbound-item-descriptions
description: "Où vivent les descriptions d'objets Unbound (table items 0x876074 stride 44, ptr desc +0x14) et comment corriger Repousse/Antigel"
metadata:
  node_type: memory
  type: project
  originSessionId: 0c9218c5-2e59-4957-9dcf-522b83124496
---

Les descriptions d'objets Unbound NE sont PAS dans le bloc FireRed 0x3D5xxx (legacy, non lu). Le moteur lit la **table items CFRU à 0x876074, stride 44**, pointeur de description `const u8* à base+0x14`. Le build FR relocalise souvent ces descriptions en free space (ex. 0xB3Fxxx, 0x16Exxx) et met le pointeur à jour — un check à offset fixe les rate, il faut **suivre le pointeur vivant**.

IDs (table étendue, les Balls passent avant → décalés vs FireRed) : Antigel=0x19, Sup. Repouss=0x5C, Repousse Max=0x5D, Repousse=0x5F.

Pour corriger une description : trouver l'offset source dans `combined_fr.txt` (les Repousse étaient à 0x3D62DF/0x3D6318/0x3D639C ; le build relocalise), éditer là, relancer la chaîne (apply_combined_fr --extend → 09_csv_to_json_v2 `<csv>` --extend → make build-fr). Antigel n'était PAS dans combined → ajout à 0xB3FF00 (last-wins, bloc bas). Voir [[unbound-fr-build-lives-in-gba-translator]] et [[combined-fr-duplicate-offsets-last-wins]].

⚠️ `09_csv_to_json_v2.py` sans argument lit un CSV template par défaut (0 traductions) → toujours passer `output/translation/<date>_trilingual_translation.csv`.

Garde e2e : `gba_translator/tests/e2e/test_item_descriptions.py` décode les pointeurs (Antigel = dégel, Repousse = « pas » pas « étapes »).
