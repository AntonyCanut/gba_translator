---
name: unbound-bounty-mission-3line-box
description: "Bounty/mission descriptions render in a narrow non-scrolling 3-line box; the generic builder mangles them with dialogue rewrap + {SCROLL}"
metadata:
  node_type: memory
  type: project
  originSessionId: 4c94ef4c-7ffa-4d0d-a2d9-73137b1f8153
---

Les descriptions de **missions** (tableau des primes Borrius) s'affichent dans une fenêtre
**étroite, non défilante, max 3 lignes** ; tout ce qui déborde passe sur une 4e ligne
**invisible** (mot/fin de phrase perdus — bug user : « Borrius ! » et « récupérez ce qui a
été volé » manquants).

**Énumération** : les ~85 missions appellent toutes un handler commun
`call 0x09EAF584` (octets `04 84 F5 EA 09`). Remonter du call → pointeur de titre (juste
avant le `04`) → pointeur de description (text-ptr peu après, dans les ~0x40 octets). 47 des
descriptions FR débordaient.

**Piège build** : les descriptions sont taguées `dialogue`, donc
`19_build_translated_rom_generic.py` les **re-wrappe** sur la boîte de dialogue (192 px,
2 lignes) et convertit les `\n` suivants en `{SCROLL}` (0xFA) — faux pour la boîte mission
(~176 px, 3 lignes, sans défilement). Les missions à 3 lignes EN écrites *en place*
survivaient (`rewrap_multiline` préserve) ; celles à 2 lignes EN ou relocalisées étaient
massacrées (ligne trop large + scroll).

**Calibrage boîte** (en unités `dialogue_linewrap.line_width`, = FireRed glyph widths) :
170 px rentre, 188 px wrappe → cibler **≤172 px/ligne** garantit l'affichage. Le modèle
sous-estime la vraie police mission ; se fier aux seuils observés par l'utilisateur, pas au
nombre absolu.

**Fix** : `combined_fr.txt` re-wrappé à la main (≤3 lignes, ≤172 px, `\n` seulement,
ponctuation `!?:` jamais en début de ligne) — 18 rebalances, 29 reformulations courtes
(sens/glossaire/placeholders `{STR_VAR}`/`{PLAYER}` préservés). Mais combined_fr seul ne
suffit PAS (le build re-wrappe) → patch post-build dédié
`patch_mission_descriptions_fr.py` (classe-3) lancé en dernier dans `build-fr` : encode
chaque description **verbatim** (sans rewrap/scroll), relocalise en free space, repointe via
le **site pointeur trouvé dans la ROM ANGLAISE** (scripts jamais relocalisés → cellule stable
même si le build a déjà déplacé/massacré la chaîne). Tests : `test_mission_box_3lines_fr.py`
(garde les 47 offsets ≤3 lignes dans combined_fr) + `test_patch_mission_descriptions_fr.py`.
Voir [[unbound-fr-build-lives-in-gba-translator]] et [[gba-translator-token-pipeline-pitfalls]].

**Piège récurrent (issue #49, offset 0x1F87B73, mission Zygarde/Dresco)** : un
premier correctif a remplacé un texte qui débordait par une phrase **sur une
seule ligne sans `\n`**, en comptant sur le retour à la ligne automatique du
jeu — ça passe le test (`test_mission_box_3lines_fr.py` simule ce wrap), mais
ça casse la convention silencieusement : les 46 autres descriptions du fichier
sont TOUTES découpées à la main avec `\n` explicite, jamais laissées au wrap
auto. Vu que le modèle de largeur sous-estime la vraie police mission (ligne
27 ci-dessus), une ligne "juste sous le seuil" en théorie peut déborder en jeu
sans marge de sécurité identique à celle des autres entrées. Fix : toujours
re-découper à la main en ≤3 lignes ≤172px avec `\n`, jamais s'appuyer sur le
wrap auto même si le test synthétique passe — puis vérifier le pointeur vivant
dans la ROM reconstruite (`TextDecoder.decode` sur les octets à l'adresse
repointée par `patch_mission_descriptions_fr.py`), pas seulement
`combined_fr.txt`.

**Récidive issue #115 (juil. 2026, offsets 0x1F1F8B7 Tablettes de Pierre +
0x1F87B73 Cellules Vertes)** : EXACTEMENT le même piège que #49. Un premier fix
a raccourci les deux textes mais les a écrits sur UNE seule ligne sans `\n` →
rendus verbatim → tout collé sur une ligne en jeu (retour user : « les trois
lignes s'affichent sur une seule ligne »). Fix : redécoupé en 2 lignes `\n`
explicites (162/139 px et 156/125 px, <170 px « fits »). Leçon renforcée :
`protected_entries.yaml` doit stocker la valeur AVEC `\n` en `expected` ET
lister la forme une-ligne en `forbidden` (sinon le hook re-valide la version
cassée). Toujours ajouter la forme mono-ligne en `forbidden` pour toute entrée
mission.
