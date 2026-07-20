---
name: unbound-arrow-line-start-audit
description: Audit EN-ancré flèche-en-début-de-ligne sur TOUS les dialogues (pas juste panneaux route) ; exclut icônes inline/headers/garbage
metadata:
  node_type: memory
  type: project
  originSessionId: 0490219a-686f-4c0a-8452-70e749f90fd9
---

Règle « flèche (0x79↑ 0x7A↓ 0x7B← 0x7C→) en début de ligne » = index 0 OU précédée d'un octet saut de ligne 0xFA(\l)/0xFB(\p)/0xFE(\n). Mais TOUT 0x79-0x7C n'est PAS une flèche de panneau : icônes couleur inline dans la prose (`A green {FC:0106}↑{FC:0102}` = Astuces Dresseur 0x1F72F5A/0x1F94FB5), headers de boîte de texte (`<0x0F>...<0x7C><0x08>`), et data non-texte (0xF8F50D, 0x1914E0D) ont la flèche en milieu de ligne EXPRÈS.

**Discriminateur = l'anglais.** Un offset est un « panneau » ssi l'EN à ce même offset a ≥1 flèche ET toutes ses flèches sont en début de ligne. Sinon on saute (l'EN aussi a la flèche en milieu → la version FR est fidèle). C'est ce que fait `scripts/audit_arrow_line_start_fr.py` (mode EN-ancré par défaut, `--source-only` pour le lint brut). Test : `tests/test_arrow_line_start_fr.py`.

B-74 avait corrigé le cluster worldmap 0x1F70xxx + la plupart des panneaux route ; ce ticket (P-68 slice) a comblé les 5 manqués : 0x741AF1, 0x1F721EC, 0x1F72353 (joignables) + 0x7B8908/0x7E6B88 (morts, 0 pointeur, dup off-by-one de 0x7E6B89 déjà fixé). Fix = ajout en fin de combined_fr.txt (last-wins), structure calquée sur l'EN.

PIÈGE livrabilité : un panneau dont l'EN COMMENCE par un octet flèche (0x1F72353 EN=`↑Magnolia...`) = vu 1-octet par l'extracteur → droppé par la pipeline générique → AJOUTER à `TARGETS` de `patch_worldmap_junction_panels_fr.py` (relocate+repoint). Les panneaux commençant par une lettre passent par la pipeline générique normale. Voir [[unbound-worldmap-junction-panels]] et [[combined-fr-duplicate-offsets-last-wins]].
