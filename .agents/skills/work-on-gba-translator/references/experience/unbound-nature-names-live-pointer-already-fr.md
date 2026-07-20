---
name: unbound-nature-names-live-pointer-already-fr
description: "Noms de nature (Lax/Lâche) déjà FR via pointeurs vivants — faux positif de l'offset mort"
metadata:
  node_type: memory
  type: project
  originSessionId: b6cee6f4-1ae5-4f17-a883-33cdf9f79e80
---

Les 25 noms de nature Pokémon vivent packés à 0x463DBC-0x463E5D mais ne sont
lus QUE par deux tables de pointeurs : `gNatureNamePointers` @0x463E60 (FireRed)
et la copie CFRU @0x1FE65F4. Les noms FR plus longs que l'EN (Assuré>Bold,
**Lâche>Lax**, Timide, Pressé, Jovial, Modeste, Discret, Foufou, Calme, Malpoli)
sont **relocalisés en free-space par la pipeline** et les DEUX tables repointées ;
la cellule packée d'origine garde ses octets EN mais n'est plus référencée.

→ Décoder l'offset d'origine (0x463DFA) renvoie « Lax » = **faux positif**
(cf. [[unbound-trace-live-pointer-not-original-offset]]). La vérité = suivre le
pointeur vivant : idx 9 → 0xD10CCD → « Lâche ». Vérifié : les 25 natures sont
déjà FR dans les deux tables. Ticket F-66 « Lax reste anglais » = premise erronée.

**Why:** le patch relocate+repoint dédié (patch_nature_names_fr.py, 1d770e0) a été
reverté (0ffd0fe) car placé AVANT mission/zone/worldmap dans build-fr → cascade
free-space F-50 ([[unbound-font-patch-freespace-cascade]]) ; en plus il mappait
Bold→Timide / Timid→Craintif (faux). Inutile de le retenter : la pipeline gère déjà.

**How to apply:** garde de non-régression `tests/test_nature_names_fr.py` (commit
1bc820d) suit les pointeurs vivants des 2 tables pour les 25 natures officielles ;
câblée dans `make build-fr`. Ne PAS ajouter de patch class-3 (risque cascade).
