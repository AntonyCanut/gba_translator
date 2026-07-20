---
name: unbound-nopointer-inplace-budget
description: Entrées « no-pointer in-place » (intro/récap guerre) ne peuvent PAS être relocalisées — la trad FR doit tenir dans le budget en_len (octets EN avant 0xFF)
metadata:
  node_type: memory
  type: project
  originSessionId: febf5d44-85a7-469c-b2d0-489e95ef8eae
---

Certaines chaînes (ex. récap de guerre intro **0x8cc49c** « The Kalosian army's
advantage… ») ne sont référencées par aucun pointeur 4 octets : elles sont lues
séquentiellement par le bytecode script. `prepare_fr_json.py` ne peut que les
patcher **in-place** (écrase les octets EN jusqu'au terminateur 0xFF) — jamais
relocaliser/repointer.

**Budget = `en_len`** = octets EN avant le 0xFF (pas de padding libre après). Si
`_encoded_length(fr) > en_len` → log « no-pointer entries skipped: FR too long for
in-place » → reste **en anglais**. Sinon → « recovered from ROM ».

**Fix = raccourcir la trad FR** sous le budget (repoint infaisable). 0x8cc49c :
budget 190 o ; la trad verbeuse « de l'armée de Kalos… utilisa son pouvoir pour
créer » faisait 208 o → 184 o avec « l'armée kalosienne… créa des portails ».

**Vérif** : encoder avec `src.core.text_codec.TextEncoder` + normalisation
(`\n`→nl, `\l`→0xFA, `\p`→0xFB, `…`→`...` 3 o) ; après build, décoder les octets à
l'offset dans `output/roms/GenedRom-fr.gba` et confirmer que le terminateur tombe
avant la chaîne suivante (0x8cc49c → term ≤ 0x8cc55b). Voir [[combined-fr-duplicate-offsets-last-wins]]
(le bloc minuscule en fin de fichier gagne) et [[unbound-fr-build-lives-in-gba-translator]].
