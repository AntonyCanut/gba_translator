---
name: unbound-straight-quote-is-ex-ellipsis
description: "Straight \" in combined_fr.txt = ex-ellipsis (EN byte 0xB0), not a real quote; remove wordless ones using English as ground truth"
metadata:
  node_type: memory
  type: project
  originSessionId: d4e97ada-1565-436f-b62b-6da840ecab17
---

R-09 follow-up (commit d1aaa6f). The CFRU/FireRed font byte **0xB0 renders as the
ellipsis glyph "…"**, but the `TextDecoder` maps 0xB0 → **straight** double quote
`"` (U+0022), while the genuine quote bytes 0xB1/0xB2 decode to **curly** “ / ”.
English uses 0xB0 heavily for pauses/hesitation (`You………`, `Ngh… take… my
Pokémon…`), so those became straight `"` in `combined_fr.txt`.

After the encoder fix [[unbound-guillemets-render-as-ellipsis]] (3ab66ad), straight
`"` re-encodes to a real quote glyph (0xB1/0xB2) → every ex-ellipsis now renders
in-game as a **stray quote with no word inside** (`Meurs""""`, `perdu"`). User:
"guillemets sans mots à l'intérieur → simplement supprimés."

**Ground truth = the English source, NOT structure.** Sequential pairing of straight
`"` makes false word-pairs (`prends" … mes Pokémon"`). Per entry, decode EN
(`input/roms/englishrom.gba`, EN offset = combined_fr offset) and count decoded
`"` (=0xB0 ellipsis) vs “/” (=0xB1/0xB2 real quote):
- EN ellipsis only, no real quote → strip ALL straight `"` (these are the wordless ones).
- EN real quote only → keep (genuine: `"passionné"`, `"Plateau Foudre"`, `"Braille"`).
- EN both (6 entries) → hand-verified; 3 keep, 3 remove (real quote already raw `<0xB1>..<0xB2>`).

Tool: `scripts/clean_wordless_quotes_fr.py` (dry-run/--apply); a `"` between two
word-chars → single space (avoid gluing `Euh"go"Floe"`→`Euh go Floe`), else delete +
tidy spaces. Strings only shrink → pointer-safe. 115 entries / 250 quotes removed.
Curly “ ”/« » untouched (always enclose a word/var). Verify decoded ROM bytes, not
the file. Note: ellipsis char `…` itself = `...` = 3×0xad, never 0xB0 [[unbound-ellipsis-no-single-byte]].
