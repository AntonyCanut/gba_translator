---
name: unbound-fr-toponym-canon
description: "Canon v3 des noms de lieux FR d'Unbound (2026-07-01) — supersede v2 ; scripts/rename_toponyms_v3_fr.py (delta v2→v3)"
metadata:
  node_type: memory
  type: project
  originSessionId: 2fb9d118-4fae-4b33-8774-a71630428a08
---

Canon **v3** des lieux FR d'Unbound (follow-up « Traductions des lieux v2 »,
2026-07-01) — REMPLACE le v2. Appliqué en **delta v2→v3** (le combined était déjà
en v2) via `scripts/rename_toponyms_v3_fr.py` (683 subs / 588 lignes, idempotent,
gardes homonymes/articles héritées de v2).

Changements v2 → **v3** : Rive-d'Automne→**Rivapolis** · Bellinbourg→**Bélenbourg**
· Cratéria→**Cratéris** · Épidimi→**Épidia** · Bourg-Tel→**Automnia** (élision
« d'Automnia ») · Vivillis→**Viville** MAIS Vivill Woods=**Bois Vivill**,
Warehouse=**Dépôt de Viville** · Polder sur Rive→**Polderive** · Cube Sarl→**Cube
SARL** · Bois Lugubres→**Boissombre** (articles consommés) · Chenal Cuivré→**Chenal
Aubrun** · Champs de Magnolia→**Champs Magnolia** · Forêt de Rougebois→**Forêt
Carmin** (village reste **Rougebois**) · Île Pleine/Nouvelle Lune→**Île
Pleinelune/Nouvellune** · Volcan Cendreux→**Volcan Cendré** · Pic Grondant→**Mont
Foudroyant** · Gouffre Glacial→**Gouffre Gelé** · Grotte Falaise→**Grotte Faille**
· Autoroute KBT / SES Expressway→**Autoroute RBT** (+ acronyme « KBT = King Borrius
the Third » → « **RBT = Roi Borrius Troisième** ») · S.S. Marine→**Marine**.

Inchangés depuis v2 : Cimistral, Naville, Antésia (Port/Égouts d'Antésia),
Daherapolis, Gurenbourg, Somnia (+ **Manoir Somnia**, déjà sans « de »), Cimes
Gelées, Zone de Combat, Base Ombre, Ruines du Néant, Tunnel Perdu, Territoire
Noirépine, Pic Cristal, Route Victoire, Tombeau de Borrius, Monde Distorsion,
Dresco, Grand Désert, Marais Fulica, Grotte Glaçon/Vallon, Mont Givre…

PIÈGE : « Cinder Volcano Depths → Tréfonds Cendrés » n'a **aucune string cible**
(absent de combined_fr.txt ET de l'extraction EN) → rien à renommer, ne pas fabriquer.
Les 2 « Black Ferrothorn » restants = dialogue de gang (≠ lieu), hors périmètre.

**Layers à synchroniser** (sinon régression build/test) : (1) `combined_fr.txt` ;
(2) TARGETS verify-fragments de `patch_zone_names_fr` / `patch_worldmap_labels_fr` /
`patch_worldmap_junction_panels_fr` ; (3) `check_translation_integrity.py`
CRITICAL_LABELS (+ forme v2 ajoutée en `forbidden` = garde régression) ; (4) tests
`test_location_names_{fr,combined_fr,e2e}` (tables + asserts par méthode + un assert
SOUS-CHAÎNE « Grondant »→« Foudroyant » dialogue PNJ ptr@0x7C252E) + `test_region_info_fr`
(EXPECTED_FR blurb) + `test_patch_{zone_names,worldmap_labels}` (combined mock DOIT matcher
les nouveaux TARGETS sinon `verify()` échoue). Tous les labels v3 tiennent in-place :
le writer utilise la capacité **padding-aware**, pas seulement en_len (Mont Foudroyant
15 o ≤ slot 28). Build `make prepare-fr && make build-fr`, vérifier les bytes décodés dans
la ROM. Suite non-émulateur verte (1184). Voir [[unbound-fr-build-lives-in-gba-translator]],
[[combined-fr-duplicate-offsets-last-wins]], [[singularity-build-resets-worktree]].
