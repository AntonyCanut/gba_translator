---
name: unbound-costume-box-menu-leading-space-and-budget
description: Garde-robe (Costume Box) menu title/buttons — combined_fr.txt parser eats leading spaces + no-pointer byte budget dropped translation to English
metadata:
  node_type: memory
  type: project
  originSessionId: 51c9090f-27c5-4670-b9fa-23bcb12dce94
---

0x1EED1B3 (title) and 0x1EED1C0 (D-pad/action/B-button labels) are fixed-width
no-pointer in-place cells (no relocation possible) in the Costume Box / wardrobe
menu. Two independent bugs, both invisible from reading `combined_fr.txt`:

1. **`apply_combined_fr.py`'s `LINE_RE` (`^\s*0x...\s*:\s*(.*)$`) strips ALL
   leading whitespace after the colon.** Editing "two leading spaces" → "one
   leading space" in the file has ZERO effect on the injected string — both
   parse to no leading space at all. EN (`" Costume Box"`) and ES
   (`" Atuendos"`) both keep a real leading space because the window chrome
   overlaps the first tile and clips it; without that space the first letter
   renders hidden ("Garde-robe" → visually "arde-robe"). Fix: force it past
   the parser with a raw byte token, `<0x00>Garde-robe` (0x00 = space in the
   CFRU charmap) — `<` is not whitespace so the regex stops eating there.

2. **Byte budget for no-pointer cells is real and silent.** 0x1EED1C0's true
   EN-measured budget (from `englishrom.gba`, not the JSON's `length` field
   which is unreliable raw-char-count) is 24 bytes total — 3× 2-byte icon
   codes + 2 spaces + terminator + **15 bytes for the three words combined**.
   `"Choisir/Essayer/Fermer"` (~20 chars) blew this, got `too_long: true` in
   the injection JSON, and silently fell all the way back to English at
   build time (no relocation attempted despite 2-3 pointer referrers found by
   byte-scan — this cell is proven non-relocatable by the ES reference ROM,
   which also kept it in-place at exactly 24 bytes: `Mov./Elegir/Salir`).
   Fixed with `Voir/Choix/Fermer` (15 chars exactly). Used raw
   `<0xF8><0x0B>`/`<0xF8><0x00>`/`<0xF8><0x01>` icon tokens rather than
   brace-style `{DPAD_LEFTRIGHT}` out of caution, though for this specific
   offset it's moot either way: this cell is non-relocatable (proven
   in-place in the ES reference ROM too), and brace tokens ARE correctly
   resolved by `_apply_control_placeholders` in the real build pipeline for
   non-relocated cells — see [[unbound-move-status-header-budget-and-token-false-alarm]].
   The literal-token risk in [[unbound-brace-control-token-relocation-literal]]
   is specifically about strings that DO get relocated.

**How to verify this class of bug**: never trust `combined_fr.txt` content or
the JSON's `length`/`too_long` fields alone — decode the actual ROM bytes at
the offset after a full `make build-fr` (`text.decoder.decode_string`), and
compute the real budget from `englishrom.gba` via `TextEncoder.encode_pokemon`
(count includes the 0xFF terminator). Regression guard:
`gba_translator/tests/unit/test_costume_box_menu_budget_fr.py`. Same pattern
as [[unbound-a4c200-stat-change-pattern-c-fix]] and
`test_dresco_mystherbe_dialogue_budget_fr.py` for no-pointer in-place budgets.
