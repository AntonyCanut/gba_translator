---
name: unbound-ellipsis-no-single-byte
description: "Le « … » n'économise PAS d'octets dans le build FR — l'encodeur le réécrit en trois points"
metadata:
  node_type: memory
  type: project
  originSessionId: bb349c3b-3176-4772-81a1-3f8386127d01
---

Dans le build FR d'Unbound, il n'existe **aucun glyphe ellipsis sur un seul octet**.
`gba_translator/src/core/text_codec.py` (ENCODE_ALIASES) mappe `…` → `...`, et
`BYTE_TO_CHAR` ne contient aucun octet décodant vers `…`. Donc `…` et `...`
produisent des octets ROM **identiques** (trois fois `.` = 0xad).

**Why:** un ticket demandait de remplacer `...` par le caractère spécial `…` « pour
gagner 2 caractères ». Cette prémisse est fausse pour ce build : le gain d'octets
ne vient QUE du retrait des doublons/rangées de points (`……`, `… … … …`), pas du
caractère lui-même.

**How to apply:** pour réellement réduire la taille des dialogues, supprimer les
ellipses surnuméraires (runs), pas convertir `...`→`…`. La conversion `...`→`…`
reste utile pour la cohérence de style de `combined_fr.txt` (déjà ~2247 entrées en
`…`) mais elle est neutre en octets. Outil : `scripts/clean_ellipsis_fr.py`
(commit f037e7e, branche unbound). Voir [[unbound-fr-build-lives-in-gba-translator]].
