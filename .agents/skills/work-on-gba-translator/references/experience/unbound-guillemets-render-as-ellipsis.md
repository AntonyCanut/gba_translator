---
name: unbound-guillemets-render-as-ellipsis
description: "RÉSOLU À LA RACINE (commit 3ab66ad) : l'encodeur mappe désormais les guillemets « » / \" \" / \" \" sur 0xB1 (“) / 0xB2 (”), plus sur 0xB0 = glyphe ellipse. Ne plus retirer les guillemets pour éviter les « … »."
metadata:
  node_type: memory
  type: reference
  originSessionId: e77ccaac-0e37-46f2-8fc4-8a9317ac018b
---

**Cause racine (historique) :** dans `gba_translator`, l'encodeur
(`src/core/text_codec.py` + `src/text/charmap_data.py`) mappait `«`, `»`, `"`, `“`,
`”` **tous** sur l'octet **0xB0**. Or 0xB0 dans la police FireRed/CFRU est le glyphe
**ellipse « … »**. Donc tout `« mot »` s'affichait en jeu comme `… mot …`. Les vraies
guillemets courbes de la ROM d'origine sont **0xB1 (“) / 0xB2 (”)** — la ROM anglaise
les utilise elle-même (`<0xB1>evolution this<0xB2>`, comptés 119/119 dans 0x1F00000-
0x1F80000), donc les glyphes existent bien dans la police livrée.

**FIX RACINE (commit 3ab66ad, branche `unbound`) — fait, ne PAS refaire de
suppression manuelle :**
- `text_codec.py` : ajout `'“':0xB1, '”':0xB2` à POKEMON_TABLE ; ENCODE_ALIASES
  mappe `«`→“ et `»`→” (ouvrante→0xB1, fermante→0xB2) ; nouvelle fonction
  `_resolve_straight_double_quotes()` transforme les `"` droits ambigus en “ ”
  alternés (ouvrante/fermante). 1 octet → 1 octet, **pointeurs inchangés**.
- `charmap_data.py` : `'“':0xB1, '”':0xB2, '«':0xB1, '»':0xB2` (les courbes avant les
  guillemets → BYTE_TO_CHAR décode 0xB1→“ 0xB2→”). Régénérer les TS :
  `python3 scripts/sync_charmap.py` (emulator-web + e2e-playwright/helpers).
- Tests : `tests/test_text_codec.py` (garde-fou encodeur) + `tests/e2e/test_quote_glyphs_fr.py`
  (décode la ROM bâtie : dialogues Zygarde « cellules »/« noyaux » portent 0xB1/0xB2,
  zéro 0xB0). `make test` 416 ✓.

**Important :** 0xB0 n'est **plus jamais émis** par l'encodeur FR (l'ellipse voulue
s'écrit `…`/`...` = 3×0xad — voir [[unbound-ellipsis-no-single-byte]]). Donc plus
besoin de retirer les `« »` ; les laisser, ils rendent de vraies guillemets.

**Antérieur (R-09, transfert PC, commit dbc2afe) :** retrait manuel des `« »` autour
des noms de Boîte (0x1A5CF1 / 0x1A5D31 / 0x1A5D6E / 0x1A5DB1 / 0x1F682A6) — palliatif
remplacé par le fix racine ; ces 5 entrées restent sans guillemets (rendu « la Boîte
Box1. », correct). Voir [[unbound-fr-build-lives-in-gba-translator]].
