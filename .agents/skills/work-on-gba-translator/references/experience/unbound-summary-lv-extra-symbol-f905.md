---
name: unbound-summary-lv-extra-symbol-f905
description: "Résumé « Lv »→« N. » RÉSOLU (B-508) — icône extra-symbole F9 05, PAS glyphe ni chaîne 0x4160F4"
metadata:
  node_type: memory
  type: project
  originSessionId: 4c56b867-d223-4d3f-9ff9-1e586ac76ba0
---

Écran Résumé/Infos Pokémon « Lv » (header + mémo) = **symbole extra FRLG #5**,
octets bruts `<0xF9><0x05>` (EMOJI=0xF9, index 5) — une ICÔNE, pas un glyphe de
police ni la chaîne Panthéon `0x4160F4` (B-236) ni la ligature party `0x1ECFA0`
(F-114). Tous écartés empiriquement (captures avant/après mGBA).

- **Header « Lv10 »** : chaîne autonome `gText_Lv` = `F9 05 FF` @ `0x416223`
  (4 pointeurs vivants). Chaîne distincte que B-236 n'avait jamais testée.
- **Mémo « au Lv 10. »** : templates lieu-de-rencontre, `<0xF9><0x05>` inline
  via jeton **positionnel** `{LV_2}`. PAS corrigeable par combined_fr : le
  builder (`_replace_placeholders`) dépile la séquence anglaise suivante pour
  CHAQUE `{token}` sans regarder son nom → retirer `{LV_2}` désync le `{LEVEL}`.

**Fix** = patch post-build `languages/fr/patches/summary_lv_labels.py` : réécrit
`F9 05` → `C8 AD` (« N. », même longueur, niveau préservé) sur (1) la chaîne
`gText_Lv` isolée `FF F9 05 FF` avec pointeur vivant, (2) chaque site
`F9 05 00 F7` (Lv+espace+niveau dynamique). Câblé en fin de `make build-fr`.
Test `test_encounter_info_fr` : octets attendus `f90500f7`→`c8ad00f7`.

Leçon : « c'est une icône donc pas éditable en texte » est FAUX — remplacer les
2 octets de l'icône par du texte « N. » (même longueur) marche. Vérif mGBA :
savestate slot 2 → START → Pokémon → A → A. Voir [[unbound-lv-level-abbreviation-fixes]],
[[unbound-party-lv-is-graphic-not-font]].

**MAJ (session F-114/F-115)** : le patch `summary_lv_labels.py` était ABSENT de
`unbound` au début de la session (merge concurrent perdu, cf.
[[singularity-parent-merge-orphaned-by-child-ticket]]) — RÉ-IMPLÉMENTÉ et re-commité.
Détails vérifiés sur ROM courante : header live `gText_Lv` @0x416223 (4 ptrs, le
2e site `FF F9 05 FF` @0x134E251 est MORT, 0 ptr → skip) ; 18 sites `F9 05 00 F7`
(dont copie relocalisée live du mémo hors 0x419xxx : 0x6E0765). Test
`test_encounter_info_fr` : `f90500f7`→`c8ad00f7` dans les octets vivants.
