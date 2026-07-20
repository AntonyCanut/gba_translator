---
name: unbound-ability-names-fixed-table
description: Ability names = class-2 fixed-width 17-byte table 0xA36398..0xA376FC ; ~130 shipped EN because FR longer than EN ; fix = patch_ability_names_fr.py post-build
metadata:
  node_type: memory
  type: project
  originSessionId: 85ae1eac-15ba-483e-bda0-025602276532
---

Noms de talents (abilities) = **table à cellules fixes 17 octets**, base 0xA36398
(index 0 = "-------"), dernier = 0xA376FC "Royal Roar" (293 cellules). Pas de
pointeur → classe 2, absente du JSON d'injection ET de l'extraction ES. Le
fallback in-place de `prepare_fr_json.py` ne traduit une cellule QUE si le FR
n'est pas plus long que l'EN → ~130 talents plus longs (Ice Body→Corps Gel,
Dry Skin→Peau Sèche…) restaient en anglais alors qu'ils tiennent dans la cellule.

**Fix (B-131) :** `scripts/patch_ability_names_fr.py` (câblé dans `make build-fr`
après patch_fixed_table_names). Écrit chaque nom FR depuis `combined_fr.txt`
(vérité) dans sa cellule 17 o, validé contre `combined_en.txt`, self-heal des
variantes désaccentuées (œ→OE) via fold, + map `_PRIOR_VARIANTS` pour réécrire un
ancien nom changé. 3 noms raccourcis pour tenir ≤16 o : Pouvoir Alchimique→Force
Alchimique, Écailles Poussière→Écailles Poudre, Rugissement Royal→Hurlement Royal.

Pièges : le nom du DERNIER talent peut faire 17 o (déborde le stride en écrivant
0xFF dans la cellule suivante) → raccourcir. Weak Armor (0xA37069) reste aussi
dans `patch_fixed_table_names.py` (idempotent, les deux patchs convergent).
Voir [[unbound-weak-armor-nodulithe-fix]] et [[translating-unbound-skill]].
Build local impossible (pas de *_translation_ready.json ni extraction) → appliquer
le patch post-build directement sur la ROM committée (déterministe, e2e gate).
