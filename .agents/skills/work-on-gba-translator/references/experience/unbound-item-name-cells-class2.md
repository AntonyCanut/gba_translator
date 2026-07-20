---
name: unbound-item-name-cells-class2
description: "Noms d'objets Unbound = cellules name[14] recopiées octet-pour-octet de la source ; pipeline FR ne les touche pas → baies restaient anglaises"
metadata:
  node_type: memory
  type: project
  originSessionId: f60df3be-cb4a-4f95-b50b-ff61d1ffc1b6
---

Les **noms d'objets** vivent en dur dans la table `gItems` à **0x876074, stride 44**,
champ `name[14]` au début de chaque entrée (id u16 à +14, prix à +16, pointeur desc à +0x14).
Ce sont des **cellules class-2** : le pipeline FR les **recopie octet-pour-octet depuis
englishrom.gba** et aucune passe de traduction ne les atteint (absentes de
translation_ready.json, combined_fr.txt, extraction espagnole).

Conséquence : la source Unbound a déjà des noms FR pour soins/objets généraux
(Potion, Anti-Brûle, Antigel…) donc ils passent FR, **mais les 67 baies restaient en
anglais** (Aspear Berry, Oran Berry…). Diagnostic fiable : décoder la ROM buildée et
comparer EN==FR (FR pipeline n'y touche pas).

**Fix** : `scripts/patch_item_names_fr.py` (post-build, modèle [[unbound-item-descriptions]]
/ patch_fixed_table_names) — dict data-driven par nom anglais, réécrit byte-exact le champ
name[14] (préserve les données à +14), idempotent, ignore les objets déjà FR. Câblé dans
`make build-fr` après patch_fixed_table_names. Noms FR officiels vérifiés Bulbapedia/Poképédia
(piège : Aspear=Baie Willia, Custap=Baie Chérim, Belue=Baie Myrte, Chilan=Baie Zalis,
Spelon=Baie Kiwan — pas des translittérations). CFRU écrit "Marang Berry" (pas Maranga).

**Portée (juin 2026)** : `BERRY_NAMES` (67) + `ITEM_NAMES` (209) = `ALL_NAMES` → **276 cellules
inline** traduites (pierres d'évo, valeur, objets tenus/combat, Joyaux de type, ROM Silvally,
Modules Genesect, encens, lettres, cannes, fossiles courts, CS01-08…). **Union name[14]** : un
nom long est stocké comme **pointeur ROM 4 octets** (MSB 0x08) → ceux-là sont déjà traduits par
le pipeline (Bright Powder→Poudre Claire) ; ne traiter QUE les cellules inline (filtrer
`data[off+3]==0x08`). Hors périmètre = noms FR > 13 glyphes nécessitant relocalisation pointeur
(Méga-Gemmes, Plaques, Joyau Électrik/Ténèbres, fossiles longs). Cristaux-Z identiques en FR.

**⚠️ RÉGRESSION VÉCUE** : le commit toponymes `65190f9` a **supprimé par accident**
`patch_item_names_fr.py` + son test + ses 2 lignes du Makefile → toute la traduction d'objets a
disparu de la ROM ("je ne vois pas la traduction"). Leçon : un patch post-build est fragile —
vérifier après CHAQUE build que le script est toujours câblé (`grep PATCH_ITEM_NAMES Makefile`)
et que la ROM décodée montre 276/276 noms FR. Toujours vérifier dans la ROM, jamais dans le
fichier source.

Table secondaire gBerries (0x3DC701, noms avec 3 octets de tête ambigus) = système de
plantation, hors périmètre. "Berry Sweet" = sucrerie Alcremie, pas une baie.
Voir [[unbound-pipeline-unreachable-name-cells]] et [[unbound-fr-build-lives-in-gba-translator]].
