---
name: unbound-msgbox-rewrap-structural-gate
description: "Builder rewrap was gated on fuzzy category=='dialogue'; msgbox text tagged 'description' shipped with EN break positions → lines overflowed the box. Fix = structural gate on EN 0xFA/0xFB."
metadata:
  node_type: memory
  type: project
  originSessionId: 8954333b-945f-40b9-b558-d5246358836c
---

Ticket « textes qui s'écrivent les uns sur les autres » (2026-07-07) : dans
`gba_translator/src/translators/19_build_translated_rom_generic.py`,
`_normalize_translation_item` n'appliquait `rewrap_dialogue` que si
`category == 'dialogue'`. Or `categorize_text` (src/core/text_converter.py) est
un heuristique de contenu : un texte de boîte sans `!`/`?`/pronom et >30 chars
devient « description » → jamais rewrappé → la ligne FR/IT/DE hérite des coupures
EN et déborde la boîte (ex. panneau Inverse Trainer House 0x1F099C2, ligne 494px
pour 192px utiles : « Beaucoup viennent à Rivapolis juste p… »). ~250 FR / 245 IT
/ 320 DE entrées touchées.

**Fix** : gate structurel — `MSGBOX_STRUCT_RE = <0xF[AB]>` dans la source EN
prouve une boîte défilante, rewrap quelle que soit la catégorie. Test :
`tests/test_msgbox_rewrap_gate.py`.

**Garde indispensable (retour user)** : les panneaux de jonction (lignes ouvrant
sur une flèche 0x79–0x7C, une destination par ligne) ne doivent JAMAIS être
re-flowés — le greedy soudait les destinations et laissait les flèches en milieu
de ligne. `is_list_layout()` dans `dialogue_linewrap.py` garde ces pages
verbatim (seuls les types de coupure sont normalisés). ~70 entrées concernées.
Pokédex/objets/descriptions à fenêtre fixe = hors gate par construction (EN sans
0xFA/0xFB). Voir [[unbound-arrow-line-start-audit]].

**Pièges d'audit largeur** :
- `TextEncoder.encode_pokemon` ajoute le terminateur 0xFF → le retirer
  (`rstrip(b'\xff')`) pour une recherche de sous-chaîne.
- `decode_pokemon` rend les args des codes FC comme glyphes imprimables (ÀÉ) →
  surestime `line_widths` de ~6px/arg ; mesurer sur la forme token.
- Faux positif : cellule fantôme mi-EN/mi-FR à 0x1F3E057 avec 0 pointeur vivant
  (fragment scanner 0x1f3e0ea écrit in-place dans une cellule morte) — toujours
  vérifier `rom.count(ptr)` avant de compter un débordement. Voir
  [[unbound-trace-live-pointer-not-original-offset]].
