---
name: unbound-color-code-terms-audit
description: Auditer/corriger les termes de jeu (talents/objets/attaques/types) restés anglais DANS les codes couleur des dialogues + pièges de vérification
metadata:
  node_type: memory
  type: project
  originSessionId: ee935f07-a8de-4d24-9ad4-24900a80f9b7
---

Tickets « traduire le contenu DANS les codes couleur » (ex. B-59 « Dialogue talents »).
Les surlignages `<0xFC><0x01><0x06>…<0xFC><0x01><0x08>` (et `{COLOR}É…{COLOR}Ë` en bloc majuscule) entourent souvent des noms de talents/objets/attaques/types laissés en anglais.

**Méthode d'audit** : extraire chaque segment entouré de DEUX marqueurs couleur (un avant ET un après ; sinon on attrape le texte courant en fin de chaîne = faux positifs), puis comparer aux clés EN du glossaire `Test/Unbound/data/glossary_pokemon_fr.json` (sections ability_names/move_names/type_names/item_names, 261/574/18/224 entrées). Gérer pluriels (`Everstones`) et préfixes buffer (`<0xFD><0x03> Everstones`).

**Vérité = la table EN JEU, pas le glossaire** (cohérence avec le sac/résumé du joueur). Décoder la cellule via charmap. Collisions de noms vérifiées : **Beast Ball→« Ultra Ball »**, **Ultra Ball→« Hyper Ball »**, Iron Ball→« Balle Fer », Eviolite→« Évoluroc », Master Ball/Lava Cookie = gardés anglais en table → laisser tels quels dans les dialogues. Generic « Evolution Stone »→« Pierre Évolutive ».

**PIÈGE talents (corrigé B-59)** : le run précédent avait traduit *Unaware*→« Annule Garde » en citant la cellule 0xA36BF6 — mais 0xA36BF6 EN=**No Guard**. Le vrai *Unaware* est @**0xA36CF5 = « Inconscient »**. Toujours décoder le nom EN de la cellule (table talents stride 0x11), ne JAMAIS se fier aux offsets cités. Magic Guard=0xA36B3B « Garde Magik », Oblivious=0xA36464 « Benêt ».

**Pièges de vérification ROM** :
- `TextEncoder.encode_pokemon` AJOUTE un terminateur `0xFF` → le retirer avant `rom.count()`, sinon faux 0 pour les phrases en milieu de chaîne (suivies d'un `<0xFC>`).
- Chaînes relocalisées (`too_long`) : l'offset source garde l'ANGLAIS mort ; il faut **suivre le pointeur vivant** (chercher dans la ROM EN les 4 octets LE = `0x08000000+offset`, lire la même position dans la ROM FR → adresse réelle → décoder). Voir [[unbound-zone-name-table-vs-worldmap-labels]].
- Le reinserter **re-wrappe** les chaînes relocalisées : un terme surligné de 2 mots peut être coupé (« Pierre<\l>Stase », « Balles<\l>Fer ») — fonctionnel, cosmétique seulement. Les chaînes in-place gardent mes `\n/\l` manuels → vérifier la largeur avec `src/core/dialogue_linewrap.line_width` (budget 192 px conservateur ; la boîte tolère ~210 px en pratique).

Voir [[unbound-fr-build-lives-in-gba-translator]], [[combined-fr-duplicate-offsets-last-wins]], [[unbound-pokedex-metric-height]] (vérifier le rendu, pas les octets bruts).
