# Résumé « Lv » → « N. » — RÉSOLU (B-508)

Suite de B-236 (investigation) et F-114 (party-box glyph). L'écran **Résumé /
Infos Pokémon** (liste équipe → A → Infos) affichait « Lv » à deux endroits ;
les deux sont maintenant « N. ».

## Mécanisme réel (confirmé en jeu)

Les deux « Lv » du Résumé sont le **symbole extra FRLG #5** — les deux octets
bruts `<0xF9><0x05>` (`EMOJI`=0xF9, index 5), qui blitte une icône « Lv ». Ce
n'est **ni** la chaîne CFRU pointée `0x4160F4` (« Lv. » du Panthéon, corrigée en
B-236), **ni** le glyphe-ligature de la police d'équipe (codepoint 0x05 @
`0x1ECFA0`, F-114). Les deux avaient été écartés empiriquement par B-236 ; ce
ticket a en plus écarté la 2ᵉ copie byte-identique du glyphe d'équipe
(`0x1EB580`) par capture avant/après.

- **Header « Lv10 »** (haut-droite) : dessiné par le code depuis la chaîne
  autonome `gText_Lv` — les trois octets isolés `F9 05 FF` à `0x416223`
  (4 pointeurs vivants : `0x8046890`/`0x80469b0`/`0x8121850`/`0x813632c`).
  B-236 n'avait testé que `0x4160F4` (Panthéon) ; `0x416223` est une chaîne
  distincte, jamais testée, qui pilote bien le Résumé.
- **Mémo « … au Lv 10. »** : les templates de lieu de rencontre
  (`Rencontré à …, au {LV_2} {LEVEL}.` + variantes œuf / rencontre fatidique)
  portent `<0xF9><0x05>` inline. **Impossible à corriger via `combined_fr.txt`** :
  `{LV_2}` est un jeton **positionnel** — le builder
  (`_replace_placeholders`) dépile la séquence de contrôle anglaise suivante
  pour *chaque* `{token}` sans regarder son nom. Retirer `{LV_2}` ferait
  pointer le `{LEVEL}` final sur la séquence `F9 05` et casserait le numéro de
  niveau. La réécriture des octets finaux en place (même longueur, 2→2) est la
  seule voie sûre.

Pourquoi « Lv » survivait à tous les blanchiments de police : `<0xF9><0x05>`
lit un jeu de glyphes « extra-symboles » séparé, pas la police de dialogue
(0x201000-0x203000) ni les blocs de police d'équipe.

## Correctif

`languages/fr/patches/summary_lv_labels.py` (post-build, exécuté en fin de
`make build-fr`) réécrit `F9 05` → `C8 AD` (« N. », même longueur) :

1. La (les) chaîne(s) `gText_Lv` isolée(s) `FF F9 05 FF` avec ≥1 pointeur vivant
   → header « N.10 ».
2. Chaque site `F9 05 00 F7` (« Lv » + espace + niveau dynamique) → mémo
   « au N. 10. ». 18 sites (templates FR relocalisés + originaux/anglais
   résiduels), numéro de niveau préservé.

Idempotent, strict (octets inattendus signalés et ignorés). Aucun repointage ni
free-space nécessaire.

## Vérification

- En jeu (mGBA, savestate slot 2 → Résumé) : header « Lv10 » → « N.10 »,
  mémo « au Lv 10. » → « au N. 10. » (numéro intact).
- `tests/test_encounter_info_fr.py` : octets attendus mis à jour
  (`f90500f7` → `c8ad00f7`) ; le garde anti-régression #5 (pas de « N. »
  redondant devant l'icône) reste valide — il n'y a désormais plus d'icône.

## Reste hors périmètre

Le fix couvre le Résumé et, par cohérence, **tous** les préfixes de niveau
« Lv » du build FR (gText_Lv partagé + mémos). Les builds IT/DE conservent
l'icône « Lv » anglaise (même mécanisme `<0xF9><0x05>`) — à porter si besoin.
