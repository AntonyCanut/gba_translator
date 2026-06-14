---
name: gotchas
description: Non-obvious traps and foot-guns in gba_translator — combined_fr, LZ77, charmap, mGBA
metadata:
  type: feedback
---

**1. combined_fr.txt — last entry wins**
The file has ~957 duplicate offsets. The live/active block is a small lowercase-only section near the bottom of the file. Always add new translations there. Never add to the top block. Never use `csv.writer` to rewrite (it reformats all 30k lines and corrupts CRLF fields).

**Why:** Top entries are overridden by bottom entries at load time; rewriting the whole file breaks the CRLF-inside-field encoding the CSV requires.

**How to apply:** Surgical byte-level append/patch only. Verify the offset you're editing isn't already overridden by a later entry.

---

**2. Trilingual CSV — CRLF + LF in fields**
The trilingual CSV uses CRLF line endings globally AND has LF characters inside some field values. `csv.writer` normalizes these away. Use raw byte-level insertion only.

**Why:** Past incident: csv.writer reformatted ~30k lines and broke in-field LFs.

---

**3. Charmap must stay in sync (Python ↔ TypeScript)**
After any edit to `src/core/text_codec.py`, run `make sync-charmap-check` (or `make sync-charmap`). The TypeScript side in `emulator-web/` maintains a parallel charmap.

**Why:** Vitest tests and Playwright runtime use the TS charmap; desync causes silent rendering failures.

---

**4. test markers — don't skip the right tests**
Fast suite skips `emulator`, `rom`, `slow`, `stress`. Standard suite skips `emulator`, `stress`, `benchmark`. CI needs `rom` excluded too (no ROM files on CI). Always use the marker flags; don't use `--ignore` alone.

---

**5. Fixed tables — never relocate**
`src/core/fixed_tables.py` lists ROM regions (species names, move names, type names, etc.) that are looked up by absolute address in Thumb code. Passing `--allow-relocate` without this guard corrupts in-game lookups silently.

**Why:** Species/move name tables are referenced by pointer arrays in Thumb ASM — relocation breaks the array.

---

**6. LZ77 regression — always repair after build-fr**
After `19_build_translated_rom_generic.py` runs, LZ77-compressed image blocks can be corrupted. `repair_stable_lz77_blocks.py` and `repair_localized_lz77_blocks.py` must run. `make build-fr` does this automatically, but manual invocations skip it.

---

**7. Stale pointers — always repoint at end of build**
Text relocation leaves the old ROM addresses referenced by some pointers. `repoint_stale_text_pointers.py` must run after build. `make build-fr` includes it.

---

**8. mGBA — NEVER save in-game during test sessions**
Saving in-game overwrites the `.sav` fixture files that Playwright uses as golden inputs. This silently breaks all future Playwright tests.

**How to apply:** Use savestates only (not in-game save). Use short sessions.

---

**9. mGBA probe noise**
`Aaaaaaa`/`Fffffff` in probe output = naming-screen button mash, not real ROM text. Bridge-route disconnects = emulator flakiness, not crashes.

---

**10. Intro font missing glyphs**
The fullscreen intro font does not have `ê`, `ç`, `ù`. Avoid these in intro/title-screen text strings; use alternatives.

---

**11. Positional placeholders**
The build engine uses positional replacement — `{0}`, `{1}`, etc. in FR strings must match the original argument order. Swapping them silently produces garbled in-game text.

---

**12. FA/FB opcodes outside combined_fr**
Opcodes `FA` and `FB` are outside the token file and must not appear in combined_fr.txt entries. They are ROM code, not text tokens.

---

**13. Gendered son/daughter strings**
Son/daughter is delivered by opcode 85 at runtime. Never write "mon {fille}" — use "mon enfant" + il/elle pronoun logic instead.

**Links:** [[project-overview]] [[domain-glossary]] [[fr-pipeline]]
