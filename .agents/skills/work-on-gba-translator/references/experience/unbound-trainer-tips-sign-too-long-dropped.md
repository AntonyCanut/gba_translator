---
name: unbound-trainer-tips-sign-too-long-dropped
description: "\"Panneau illisible\" (#119) = trad FR too_long silencieusement droppée, l'anglais reste affiché"
metadata:
  node_type: memory
  type: project
  originSessionId: 7263ae06-3e6e-48ff-aafa-4f5c4c051bc4
---

Issue #119 « FR 2.1.65 - Panneau illisible » (panneau sortie ouest de Boissombre,
offset `0x1EFFD93`). Le symptôme rapporté « illisible » = le panneau affichait
**encore l'anglais** (« This Trainer Tips sign was read on the path just outside
the western Grim Woods exit. »), pas du texte corrompu.

Cause : cluster de panneaux « Trainer Tips » ~`0x1EFFC00`–`0x1F00100`, chaînes
**inline** empaquetées (chacune a UN pointeur dans la table `0x1E939D0`, stride
0x10). Le pipeline les écrit **en place** et **droppe silencieusement** toute
entrée `too_long` — il ne repointe PAS cette catégorie (`description` inline).
La trad FR précédente faisait 97o pour un slot de 86o → `too_long: true` → ignorée
→ anglais conservé.

Fix : **raccourcir la trad FR pour tenir dans le budget** (slot = distance au
pointeur suivant ; ici 86o = 85 chars + `0xFF`). Mesurer avec
`Test/Unbound` `src.text.encoder.encode_string(text, terminate=False)`. 82o a tenu :
`Panneau Conseils Dresseurs lu\nsur le chemin juste à la sortie\nouest de Boissombre.`
Vérifier `too_long: false` dans le JSON PUIS décoder les octets ROM à l'offset.
Les voisins du cluster (0x1EFFC34, 0x1EFFDE9…) restent anglais pour la même raison
(non traité ici, scope = #119 seul).

Même principe que [[unbound-nopointer-inplace-budget]]. Grim Woods = Boissombre
([[unbound-fr-toponym-canon]]). Guard : `protected_entries.yaml` + intégrité.
