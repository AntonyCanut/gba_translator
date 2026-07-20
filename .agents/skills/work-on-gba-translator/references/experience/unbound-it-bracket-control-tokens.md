---
name: unbound-it-bracket-control-tokens
description: "Italian dump uses [green]/[buffer1]/{player} bracket tokens the pipeline never converted → ?green? garbage; normalize to raw <0xNN> codes at import"
metadata:
  node_type: memory
  type: project
  originSessionId: 0c2ba8e7-864a-40d8-9f00-14d18129244d
---

The Italian community dump (`languages/it/combined_it.txt`) marks colours,
buffers and name placeholders with its OWN readable token convention, NOT the
FR `{COLOR}` convention. The build pipeline never converted them: `[ ] { }`
have no font glyph, so the encoder rendered `?green??buffer1??black?` in-game
(reported on the difficulty prompt). FR uses `{COLOR}<glyph>` (positional,
pulled from EN raw bytes); IT used `[green]` etc.

**Fix (commit 696edaf):** `normalize_control_tokens()` in
`scripts/process_italian_translations.py` (wired into `escape_text`, also
migrated the existing file) maps each token to its **raw `<0xNN>`** sequence —
self-contained, faithful to the translator's explicit colour, immune to
EN-vs-IT positional drift (raw form shrinks strings → also reduces relocation).

Mapping VERIFIED byte-for-byte vs `output/extracted/.../englishrom_texts.json`
(every clean-aligned string agreed on one code):
- Colours → `<0xFC><0x01><0xNN>`: green=06, red=04, blue=08, black=02,
  lightgreen=07, orange=05, darknavyblue=0F
- Buffers/names → `<0xFD><0xNN>`: buffer1=02, buffer2=03, buffer3=04,
  rival=06, {player}=01
- `[pause]` → `<0xFC><0x09>`

Guards: `tests/test_combined_it_format.py` (mappings + no leftover brackets),
`tests/e2e/test_italian_build.py::TestColorControlCodes`. Also kept
`patch_intro_questions_it.py` IT_TEXTS in sync (drift test).

STILL UNHANDLED (filed B-92): backslash-hex escapes `\CC`/`\07`/`\ad` (raw
arg bytes, `apply_combined` only knows `\n \l \p`) and 3 sound macros
`[pause_music]`/`[wait_sound]`/`[resume_music]`. Free-space relocation
exhaustion (2796 fails, `test_relocation_reasonable` red) filed B-91 —
pre-existing, NOT caused by colour fix. See [[unbound-fr-build-lives-in-gba-translator]],
[[gba-translator-token-pipeline-pitfalls]], [[unbound-color-code-terms-audit]].
