---
name: unbound-status-abbrev-sommeil
description: "Statut Sommeil = SOM (officiel FR), pas DOR ; deux patchs class-3 (texte + badge graphique)"
metadata:
  node_type: memory
  type: project
  originSessionId: 99ad10de-7a19-450c-b23a-763cd71a0256
---

Le statut **Sommeil** s'affiche en **« SOM »** (abréviation officielle FR), PAS
« DOR » (Dort). Le projet shippait DOR ; l'utilisateur a demandé SOM (« comme le
jeu original »). Corrigé 2026-06-22.

Le statut existe en **deux endroits distincts**, tous deux des patchs class-3
post-build wirés dans `make build-fr` (Makefile l.186-187) :

1. **Texte** — `gba_translator/scripts/patch_status_abbrevs_fr.py` : table pointeur
   `0x3DFE18` (stride 8), idx0=Sommeil. String 3 car + 0xFF (EN à 0x417914). FR
   ≤ longueur EN (in-place). `prior={"DOR"}` self-heal depuis l'ancien build.
   Autres : PSN→EMP, BRN→BRL, FRZ→GEL, PAR inchangé.
2. **Badge graphique** — `gba_translator/scripts/patch_status_badges_fr.py` :
   tuiles LZ77 4bpp, 4 blocs (0x0B1E11C/0x0B1E280/0x00E82EA0/0x00E9BF48), slot 2 =
   Sommeil. Lettres 4px×6 dans `_LETTERS` ; **glyphe « S » ajouté** (S-O-M).

**Piège** : corriger le texte (0x3DFE18) ne corrige PAS le badge de combat — ce
sont deux familles d'octets séparées. Le symptôme « SLP en combat » vient du badge
graphique, pas de la table texte. Vérifier le badge en décompressant le bloc et en
rendant les pixels du slot en ASCII (pixel 0x2=lettre, 0x9=bordure).

Tests : `test_patch_status_abbrevs_fr.py`, `test_patch_status_badges_fr.py`
(gba_translator) ; `tests/e2e/test_status_and_type_encoding.py` (Test/Unbound,
lancer avec `.venv/bin/python` — le python3 système 3.9 casse sur `X | None`).
Voir aussi [[unbound-type-icons-are-graphics]].
