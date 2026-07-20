---
name: unbound-level-marker-memo-space-rotation-fix
description: "Issue #66 'N. 14' au lieu de 'N.14' — le mémo Résumé gardait un octet espace littéral après l'icône Lv; fix = rotation de l'octet en fin de chaîne, pas suppression (longueur figée)"
metadata:
  type: project
  originSessionId: 92376f87-2675-4587-b508-0b363d3c8edf
---

Suite de [[unbound-summary-lv-extra-symbol-f905]] / [[unbound-lv-level-abbreviation-fixes]] :
le fix B-508 (« Lv »→« N. ») avait bien réglé le header du Résumé (« N.10 », jamais
d'espace) mais le **mémo bas-d'écran** (« Rencontré à…, au N. 10. ») gardait un
octet espace **littéral** (`0x00`) entre « N. » et le niveau dynamique — structure
byte-exacte confirmée par `tests/test_encounter_info_fr.py` :
`c8(N) ad(.) 00(space) f7(ctrl) 01(param) ad(.) ff(term)`. Ça rendait « N. 14 »
au lieu de « N.14 », décalant les chiffres vers la droite (issue #66).

**Piège** : ce patch (`languages/fr/patches/summary_lv_labels.py::_patch_memos`)
tourne post-build, en place sur le ROM final, **sans repointage**. Supprimer
l'octet espace raccourcirait la chaîne de 1 octet → décalage de TOUS les octets
suivants du ROM entier (`bytearray[a:b] = shorter` en Python redimensionne le
tableau) → corruption catastrophique de pointeurs/code absolus.

**Fix correct** : *rotation*, pas suppression. Puisque la chaîne se termine
toujours par `0xFF` juste après un point final (`ad`), on déplace l'octet espace
de sa position (juste après « N. ») vers la toute fin (juste avant `0xFF`) —
même longueur totale, l'espace de fin est invisible (trailing whitespace).
Implémentation : trouver le terminateur `0xFF` depuis la position de l'icône,
puis `segment = rom[space_pos:end]; rom[space_pos:end] = segment[1:] + b'\x00'`.

Idempotence : la fonction boucle sur DEUX préfixes candidats (`LV_SYMBOL` ET déjà
`ND_TEXT`) pour couvrir aussi bien un ROM encore anglais qu'un ROM patché par
l'ancienne version du script (icône déjà remplacée mais espace pas encore
déplacé) — sinon un ROM partiellement reconstruit garderait le bug.

Vérification sans rebuild complet : ROM déjà committé (`output/roms/GenedRom-fr.gba`,
32 Mo, tracké git) + `make extract-en` (rapide, ne nécessite pas tout le pipeline
FR) suffisent à faire tourner `tests/test_encounter_info_fr.py` en conditions
réelles — pas besoin de refaire toute la chaîne `apply_combined_fr → CSV → JSON
→ make build-fr` pour vérifier un patch post-build isolé. Réappliquer juste
`python3 languages/fr/patches/summary_lv_labels.py --rom <copie>` sur le ROM
déjà buildé donne un résultat identique à un rebuild complet (déterminisme du
build, cf. [[unbound-build-determinism-relocation-order]]) puisque seule la
dernière étape de la chaîne a changé.

Faux positifs à ignorer : `pytest -m rom` fait aussi tourner
`tests/e2e/fr/test_nodulithe_passive.py` qui skip/échoue si
`output/translation/*_translation_ready.json` est absent (fichier daté,
gitignoré, généré seulement par le pipeline CSV complet) — échec pré-existant
sur la branche `unbound` elle-même dans un worktree sans pipeline complet,
sans rapport avec ce fix.
