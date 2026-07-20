---
name: unbound-battle-placeholder-positional-vs-named-fd-codes
description: "gba_translator's {brace} placeholders in battle-string combined_fr.txt entries used to resolve by POSITION (Nth brace = Nth EN control code), not by name — renaming/reordering braces was a silent no-op; partially fixed by"
metadata:
  node_type: memory
  type: project
  originSessionId: eed0cec4-5566-46b5-b60c-5ec5e9e73ed1
---

Issue #124 ("Chamallot de Attaque ne baisse pas" instead of "Attaque de Chamallot
ne baisse pas !", Guard-Dog-style ability at `combined_fr.txt` offset `0xA4B2F9`):
the entry was `{UNKNOWN_STR} de {B_SCR_ACTIVE_NAME_WITH_PREFIX}\n...`. Swapping
which name came first (`{B_SCR_ACTIVE_NAME_WITH_PREFIX} de {UNKNOWN_STR}`) had
**zero effect on the built ROM bytes** — same output both times.

**Why:** `src/translators/19_build_translated_rom_generic.py`'s
`_replace_placeholders` (and `scripts/apply_combined_fr.py`'s twin) used to pop
control-code sequences off a FIFO queue built from the *English* source string,
in the English string's left-to-right order, one per `{...}` encountered in the
translation — **regardless of the name inside the braces**. Two braces in the
same left-right positions always got the same two EN control codes in the same
order, no matter what you called them.

**Fix landed independently as #123** ("resolve battle {B_*} placeholders by
name, not position"): added `FD_VARIABLE_CODES` (name → fixed `<0xFD><0xNN>`
byte, per `docs/17_TEXT_VARIABLES.md`) and `_pop_named_sequence`, which pops the
EN sequence matching a **known** name's fixed code first; only a placeholder
whose name isn't in that table still falls back to positional FIFO on the
*remaining* pool.

**Residual gap:** `UNKNOWN_STR` (used for a battle stat name in generic
"stat won't lower/rise" templates) is NOT in `FD_VARIABLE_CODES` — it has no
fixed code, so it still resolves positionally. In a 2-placeholder string where
the other placeholder IS a known name (e.g. `B_SCR_ACTIVE_NAME_WITH_PREFIX` =
`0x13`), by-name resolution removes the known one first, so the leftover
placeholder unambiguously gets whatever's left — reordering braces now works
correctly in that 2-variable case post-#123.

**How to apply:** if a battle-message translation reports a "variables
inversées" bug, first check if `#123` already fixed it for that placeholder
pair (look for the name in `FD_VARIABLE_CODES`). If unsure or to sidestep the
whole brace-resolution mechanism entirely, use explicit `<0xFD><0xNN>` raw hex
tokens in `combined_fr.txt` instead of `{name}` braces — TextEncoder parses
`<0x..>` directly (bit-for-bit, order exactly as written), immune to any
positional-vs-named resolution logic. Get the exact byte for a script/battle
variable from `docs/17_TEXT_VARIABLES.md` or by decoding the EN ROM's raw bytes
at that offset with `_extract_control_sequences_from_raw`-equivalent logic.

Also re-confirms [[unbound-make-build-fr-reuses-stale-same-day-json]]: editing
`combined_fr.txt` a *second* time in the same session requires rerunning
`apply_combined_fr.py --extend` + `09_csv_to_json_v2.py` again before
`make build-fr` — otherwise the build silently reuses the JSON generated from
the *first* edit (same day → same filename → "already has entries" skip).
Always decode the ROM bytes at the target offset after rebuild to confirm,
never trust the integrity-guard's textual `[OK]` line alone (it only checks
`combined_fr.txt` resolves to `expected`, not that the ROM bytes match).

See [[translating-unbound-skill]], [[unbound-stat-change-baked-verb-b35-not-pure-buffer]],
[[unbound-battle-stat-change-effect-text]], [[gba-translator-token-pipeline-pitfalls]].
