---
name: unbound-battle-stat-change-effect-text
description: "Combat stat-change messages (\"Attaque de Pikachu augmente !\") — buffer order, brace-vs-<0x> token trap, and the \"source fixed but ROM never rebuilt\" failure"
metadata:
  node_type: memory
  type: project
  originSessionId: d10a1a6e-eccf-4ae4-9c73-cd431c8c6ade
---

Ticket B-35 "Combat Textes effets". The in-battle stat-change templates live at
`combined_fr.txt` offsets 0x3FCB5F/6A/8F/9A (atk/def × up/down) plus verb
0x3FCB4A "augmente !" / 0x3FCB59 "baisse !" and intensity modifier 0x3FCB41 /
0x3FCB50 ("beaucoup", ex-EN "sharply "/"harshly ").

Buffer map (verified by decoding EN ROM at 0x3FCB5F = `FD 0F B4 E7 00 FD 00 FE FD 01`):
- `<0xFD><0x00>` = stat name, `<0xFD><0x0F>` = attacker name, `<0xFD><0x10>` =
  defender name, `<0xFD><0x01>` = verb. EN reads "[NAME]'s [STAT]"; correct
  French is "[STAT] de [NAME]" → `<0xFD><0x00> de <0xFD><0x0F>\n<0xFD><0x01>`.

Two traps that made this "inverted" complaint recur 3 times:
1. **The ROM was never rebuilt.** The source order had been corrected in a prior
   commit but the playable ROM still carried the OLD inverted strings (relocated
   to free space + repointed at an earlier build). A committed source fix that
   isn't rebuilt never reaches the game. ALWAYS rebuild and decode the bytes the
   engine reads — follow the pointer (e.g. site 0x3FE260 → relocated target),
   not the original offset, since too-long FR strings get relocated.
2. **Brace `{FD00}` syntax is NOT understood by the encoder** (`src/core/text_codec.py`
   only parses `<0x??>`). Braces get written as literal chars → 23 bytes of
   garbage → too_long → still injected by 19_build (which DOES expand `{FDxx}`),
   but csv_to_json mis-measures length. Use `<0xFD><0x00>` form to be safe and to
   keep length honest. (Plain dialogue `{B_ATK_NAME_WITH_PREFIX}` named tokens are
   fine — 19_build maps those.)

Modifier spacing: EN "sharply " had a trailing space that separated it from the
verb on concat ([modifier][verb]). FR "beaucoup" lost it → "beaucoupaugmente !".
Fix = explicit space byte `beaucoup<0x00>` (line tooling trims literal trailing
spaces).

**±2 word order SOLVED text-only (commit 3050eef, follow-up to B-35).** Engine
builds buff `<0xFD><0x01>` = `[modifier?]+[verb]`, modifier ALWAYS prepended, so
"beaucoup augmente !" was unavoidable WHILE the verb lived in the buffer. Earlier
note said this needed a Thumb patch — WRONG. Trick: templates 0xC9/0xCA(=0x3FCB5F/
6A) are RISE and 0xCB/0xCC(=0x3FCB8F/9A) are FALL (FireRed STRINGID enum 201-204,
confirmed by adjacent stat-id tables {0xC9,0xCA}/{0xCB,0xCC} @0x454082/0x454070).
So bake the conjugated verb INTO the templates ("…\naugmente <0xFD><0x01>" /
"…\nbaisse <0xFD><0x01>") and shrink the verb buffer (0x3FCB4A/0x3FCB59) to just
`!`. Keep modifier `beaucoup<0x00>`. Now buff = modifier+"!" lands AFTER the verb:
+1 "augmente !", +2 "augmente beaucoup !", −1 "baisse !", −2 "baisse beaucoup !".
No empty strings (those get dropped) — the "!" carries the buffer. Generalizable:
when the engine prepends a fixed buffer in the wrong order, move the invariant
word into the (direction-split) template and reduce the buffer to the variable tail.

Gotcha: `09_csv_to_json_v2.py` REQUIRES the explicit CSV path
(`output/translation/2026-01-15_trilingual_translation.csv`); with no arg its
`_find_latest_csv` globs `*_translation_*.csv` which misses
`..._trilingual_translation.csv` and silently picks an empty template → 0
translations. See [[unbound-fr-build-lives-in-gba-translator]],
[[gba-translator-token-pipeline-pitfalls]], [[unbound-battle-name-with-prefix]].

Regression test: `gba_translator/tests/test_battle_stat_change_order_fr.py`.
