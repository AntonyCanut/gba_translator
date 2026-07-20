---
name: unbound-special-text-rules
description: Règles des textes plein écran Unbound (intro/crédits) et glyphes accentués indisponibles
metadata:
  node_type: memory
  type: project
  originSessionId: 666a9555-b337-418a-b166-c262adde919b
---

Textes spéciaux Unbound (intro, cinématiques, crédits, lettres, puzzles) : la source EN n'utilise QUE des `\n` (≥2, jamais `<0xFA>/<0xFB>`) + lignes vides de centrage. Détection `is_multiline_layout()` / rewrap `rewrap_multiline()` dans `src/core/dialogue_linewrap.py` de gba_translator (cap = ligne EN la plus large). Ne jamais leur appliquer la règle dialogue 2-lignes.

Glyphes (corrigé juin 2026, commit f903cae de gba_translator) : les polices d'Unbound (dialogue ET plein écran intro) rendent TOUT le charmap Gen III international standard — vérifié par sondes mGBA avec ROM de test glyphe par glyphe. À=0x01 Ç=0x04 È=0x05 É=0x06 Ê=0x07 Ë=0x08 Î=0x0B Ï=0x0C Ô=0x0F Œ=0x10 Ù=0x11 Û=0x13, ê=0x1C ë=0x1D ï=0x21 ô=0x24 œ=0x25 ù=0x26 û=0x28. Les anciennes croyances « pas de ê/ç/ù dans l'intro » venaient de codepoints NON standard (ù=0x7F vide, É=0x84 = « ᵉ » exposant, 0x82/0x83 vides). Seuls les umlauts ä/ö/ü/ÿ n'ont pas de glyphe (aliasés). Les reformulations d'intro pour éviter ù/ç/ê ne sont plus nécessaires.

Voir [[unbound-fr-build-lives-in-gba-translator]] pour la chaîne de build.
