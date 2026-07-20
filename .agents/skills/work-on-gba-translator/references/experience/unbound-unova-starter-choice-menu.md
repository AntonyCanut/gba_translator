---
name: unbound-unova-starter-choice-menu
description: "Choix des 3 starters d'Unys (PNJ Borrius) — noms de starters dans un multichoice = strings pointeur séparées de la table d'espèces"
metadata:
  node_type: memory
  type: project
  originSessionId: 1829cb0c-9329-4175-85ea-087975136ee9
---

Le PNJ de Borrius qui donne un starter d'Unys affiche un menu de choix dont les
3 options sont des **strings texte indépendantes** (pas la table de noms
d'espèces) : `0x1F63D68 {COLOR}É Snivy`, `0x1F63D71 {COLOR}Ê Tepig`,
`0x1F63D7A {COLOR}Ë Oshawott`. Format = `{COLOR}<octet>` + nom (FC 01 + valeur
couleur É=06/Ê=07/Ë=08). Seul Oshawott→Moustillon était dans `combined_fr.txt`
→ le menu montrait « Snivy / Tepig / Moustillon ». Fix = ajouter les 2 options
manquantes (Vipélierre/Gruikui) + le message de confirmation `0x7E6816`
(« You received a Snivy, Tepig, and Oshawott ») resté 100% anglais.

Ces options sont **too_long** (FR > EN) → relocalisées+repointées par le build :
elles atterrissent en cluster contigu en free space (0xC42448) et le tableau de
pointeurs du multichoice (`0x1EC9458/5C/60`, 3 ptrs consécutifs 4 o) est mis à
jour. Vérifier en suivant le pointeur live, pas l'offset d'origine. Test source
`test_unova_starter_choice_combined_fr.py`. Voir [[unbound-fr-build-lives-in-gba-translator]].

**PIÈGE vérif** : un grep d'octets à plat sur le message de confirmation rate la
chaîne car le wrapper insère un `0xFA` (saut de ligne) au milieu.
