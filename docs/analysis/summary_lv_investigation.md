# Résumé « Lv » → « N. » (B-236) — état de l'investigation

**Contexte** : suite à F-114 (party-list « Lv »→« N. » via un glyphe-ligature de
police, `0x05` @ `0x1ECFA0`), l'écran **Résumé / Infos Pokémon** (liste équipe →
A → Infos) affiche encore « Lv » à deux endroits :
1. « Lv10 » en haut à droite, à côté de l'icône du Pokémon.
2. Le mémo bas d'écran : « Rencontré à Base Ombre, au **Lv** 10. »

## Ce qui est RÉSOLU dans ce ticket

Un troisième « Lv. » a été identifié et corrigé au passage : la chaîne CFRU
pointée `0x4160F4` (« Lv. », 2 pointeurs vivants `0x000F33D4`/`0x009F2B90`),
utilisée par l'écran du **Panthéon** (Hall of Fame) — PAS par le Résumé
(vérifié empiriquement, voir plus bas). Corrigée dans `combined_fr.txt` →
« N. ». Au passage, un doublon d'offset mort (`0x459375` au lieu du vrai
`0x459378`, décalage identique au piège documenté dans
`unbound-trace-live-pointer-not-original-offset`) laissait le tableau
Nom/Souhaité/Offre/**LLv.** (typo « LLv. » en double-L) du Salon Union non
traduit ; retargeté sur le bon offset vivant et corrigé en « N. ».

## Ce qui N'EST PAS encore résolu (mécanisme du Résumé lui-même)

### 1. Header « Lv10 » (haut-droite, à côté de l'icône)

**Éliminé empiriquement** (patch direct + capture d'écran, sans passer par le
pipeline de traduction) :
- **Pas** la chaîne CFRU `0x4160F4` : la corriger en « N. » n'a aucun effet
  visuel sur cet écran (l'écran affiche toujours « Lv10 » après rebuild) —
  cette chaîne alimente le Panthéon, pas le Résumé.
- **Pas** le glyphe-ligature de police du party (codepoint `0x05` @
  `0x1ECFA0`, fix F-114) : patcher directement ce glyphe sur une copie de la
  ROM buildée n'a **aucun effet** sur le Résumé (capture avant/après
  identique) — confirme la note de `party_menu_lv_resolution.md` : « L'écran
  Résumé... utilise un mécanisme différent ».

**Piste ouverte** : trace d'exécution (read-watch sur les tables de largeur de
police, script `scripts/probe_summary_lv_trace.mts`, réutilisant l'infra
watchpoint de F-113/bridge.lua — **note : cette infra n'existe pas encore sur
la branche `unbound` de base**, elle a été cherry-pickée depuis le commit
`b755ada` de F-113 dans ce ticket pour l'investigation). Résultat sur l'écran
Infos (une ouverture) :

| police (table de largeur) | hits | site d'appel (pc/lr) principal |
|---|---|---|
| `small@1EA100` | 1854 | pc=0x8002fb6 lr=0x80066ad — police dominante (labels No./Type/OT/IDNo/Item, texte Nature…) |
| `font@207300` | 93+10 | pc=0x80066d8/0x8006678 |
| `small@1EAF00` | 32 (r0=0 / r0=0x80000000, suspect) | pc=0x8002fb0/0x8002fa0 lr=0x80064a1 |
| `small@1EEF00` (police party, F-114) | 24 | pc=0x80064e2/0x80064b4 — probablement le surnom « Embrylex » qui réutilise la police party |
| `small@1EA600` | 8 (r0=0x1, anormal) | pc=0x8006434/0x80063e4/0x80063f6/0x80063fa lr=0x80060d1/0x8005b5b |
| `small@1E9F00` | 2 | pc=0x8001076 lr=0x800102f |

Aucune de ces tables ne correspond de façon évidente à un rendu de « Lv » (le
comptage dominant `1854×` est trop générique pour être un label spécifique).
Comme pour le party (F-113/F-114), il est probable que « Lv » ici **contourne
aussi la lecture de table de largeur** (glyphe-ligature spécial) — la piste à
suivre est un **read-watch sur les DONNÉES de glyphes** (pas la table de
largeur) des polices actives ci-dessus pendant l'affichage précis de « Lv10 »,
en cherchant le glyphe lu SANS hit de table de largeur correspondant — exactement
la méthode qui a percé `0x1ECFA0` pour le party (F-114). Candidates prioritaires
par fréquence d'anomalie : `small@1EA600` (comportement r0 atypique) puis
`small@1EA100` (police dominante de l'écran).

### 2. Mémo bas d'écran « au Lv 10. »

**Mécanisme identifié avec confiance** (analyse statique, pas encore vérifié
par patch en jeu) : le texte source dans `combined_fr.txt` (ex. offset
`0x419822`, cf. `tests/test_encounter_info_fr.py`) contient un jeton
positionnel `{LV_2}` qui n'est **pas** un texte CFRU standard — il round-trip
vers les octets bruts anglais d'origine à cette position. Décodage brut de la
séquence englobante :

```
au <0xF9>È <0xF7>À.
```

`0xF9 XX` est le préfixe **« emoji/graphic » à 2 octets** documenté dans
`src/text/control_codes.py` (`EMOJI = 0xF9`) — un code de contrôle qui blitte
une **icône graphique**, pas du texte lisible dans une table de police. Ici
`XX=0x05`. C'est très probablement le même mécanisme que les icônes de type
utilisées ailleurs par CFRU (`<0xF9><0x15>`: Bug, `<0xF9><0x16>`: Dark, voir
`tests/test_control_placeholders.py`), réutilisé pour une icône compacte
« Lv » dans les écrans d'info Pokémon (mécanique standard des jeux Gen 3 :
Emerald/FRLG affichent souvent « Lv » via une icône dédiée plutôt que du texte
sur cet écran précis).

**Ce que ça implique** : ce n'est **pas** une correction `combined_fr.txt`
possible (le texte ne peut pas remplacer une icône). Il faut localiser le
bitmap de cette icône (comme `hp_labels.py`/`party_lv_label.py` pour les
labels PV/N. du party) — table d'icônes indexée par l'argument `XX`, à
retrouver par dump VRAM + recherche de tuile, puis redessiner l'icône n°5 en
« N. » et recompresser en place si LZ77.

## Recommandation

Ces deux mécanismes nécessitent chacun le même niveau d'effort que F-113+F-114
(trace mGBA dédiée, calibration glyphe/icône, patch strict avec validation
d'octets connus, vérification en jeu) — hors budget raisonnable de ce ticket
en plus du travail déjà livré. Suivi via ticket dédié (voir gestionnaire de
tickets), avec cette investigation comme point de départ direct (tables de
largeur actives listées ci-dessus, mécanisme icône `<0xF9><0x05>` confirmé
pour le mémo).

## Outils réutilisables ajoutés dans ce ticket

- `scripts/probe_summary.mts` — capture d'écran de la page Infos (team list →
  A → A), pour vérif visuelle rapide.
- `scripts/probe_summary_lv_trace.mts` — read-watch des 11 tables de largeur
  de police pendant l'ouverture de la page Infos (voir tableau ci-dessus).
- Infra watchpoint mGBA (`bridge.lua`/`mgba-bridge.ts`) cherry-pickée du
  commit F-113 `b755ada` (absente de la branche `unbound` de base tant que
  F-113/F-114 ne sont pas mergés).
