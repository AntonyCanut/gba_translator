---
name: unbound-volcan-cendre-audit-blindspots
description: "Auditer le toponyme Volcan Cendré : le grep 'Volcan X' rate l'anglais 'Cinder Volcano', le 'Cendreux' v2 et la bannière map-popup à pointeur embarqué (B-138 rouvert)"
metadata:
  node_type: memory
  type: project
  originSessionId: 6af6a8bf-a4ff-4d44-a062-89440a44835c
---

Corriger le toponyme volcan (canon **« Volcan Cendré »**, cf. [[unbound-fr-toponym-canon]])
exige un audit **par pointeur vivant**, pas un simple `grep "Volcan [A-Za-zé ]*"`. Ce grep
(utilisé par le 1er passage B-138) exige une espace APRÈS « Volcan » et rate trois familles
de régressions bien rendues en jeu :

1. **Ordre anglais « Cinder Volcano »** — « Volcano » n'a pas d'espace suivante, « Cinder »
   précède. Deux entrées vivantes ratées : `0x1F49D19` (dialogue Hoopa), `0x74503F` (statue
   Sulfura, doublon last-wins qui avait ré-anglicisé la bonne trad de `0x5383`). Fix combined_fr.
2. **Forme v2 périmée « CENDREUX »** — `0x7D61AD` (tirade Marlon en capitales, entre codes
   `{COLOR}` donc aucun préfixe « Volcan »). Le canon v3 a remplacé Cendreux→Cendré.
3. **Bannière map-popup à pointeur embarqué** — nom `0x78D7C8` « Cinder Volcano West ».
   Struct à `0x78D7BC` = `<en-tête><ptr embarqué @0x78D7C0 → texte><champs><texte inline>`.
   Le moteur lit le nom via le **pointeur embarqué**, pas en scannant le struct. Fix =
   ajouter `0x78d7c8: Volcan Cendré Ouest` à combined_fr + `TARGETS` de
   `patch_zone_names_fr.py` (relocate+repoint, cluster fly-banner 0x78D8xx ; « Ouest » = même
   longueur 19 o que « West »).

**Audit correct** = scanner la ROM pour les bytes de « Cinder Volcano », remonter au début
0xFF, et ne garder que les strings dont le début est référencé par un pointeur vivant
(`rom.count(pack('<I', start+0x08000000))>0`). Les cellules d'origine des strings relocalisées
gardent de l'anglais MORT (refs=0) — faux positifs. Piège inverse : la bannière map-popup a
son struct (0x78D7BC) toujours vivant (ptr map-header 0xB9D86C) même après fix, donc le
garde-fou « pas de pointeur vivant vers Cinder Volcano » y donne un faux positif ; vérifier la
bannière en **suivant le ptr embarqué 0x78D7C0** (doit rendre « Volcan Cendré Ouest »).

Post-fix vérifié : 0 string « Cinder Volcano » vivante, 0 « CENDREUX », 47× « Volcan Cendré ».
Tests dans `tests/test_location_names_fr.py`. Piège worktree partagé : un `git commit` sans
pathspec embarque les changements staged d'un agent concurrent ; committer avec
`git commit -- <chemins>` et relire `git show --stat HEAD` (cf. [[unbound-pattern-c-stale-snapshot-commit]]).
