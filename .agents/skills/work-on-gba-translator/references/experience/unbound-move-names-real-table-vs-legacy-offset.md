---
name: unbound-move-names-real-table-vs-legacy-offset
description: "gba_translator move-name table — live offset is BASE-DEPENDENT: 0x1B2980 on the old FR-patched base, stock 0xA40A10 on the clean R-17 base; patch now resolves it from the ROM pointer"
metadata:
  node_type: memory
  type: project
  originSessionId: c2020be7-b356-4625-8d83-38aab7b6a1ce
---

> **UPDATE (T-38, R-17 clean base):** the "0x1B2980 is the real table" claim
> below was only true for the **French-patched** base. That base had the whole
> move-name table *relocated* to free space at 0x1B2980 with all 41 code
> pointers repointed there. On the genuinely clean R-17 base
> (`input/roms/englishrom.gba`; old file kept as `patchedfrenchrom.gba` for
> build-fr) the table sits at its **stock offset 0xA40A10** (English names) and
> 0x1B2980 is unreferenced 0xFF free space. Since IT/DE build on the clean base,
> `move_names.py` hard-coding 0x1B2980 wrote to dead space → IT shipped English
> move names. Fixed: `resolve_live_base(data)` reads the live pointer at code
> site 0x308A4 (validates index-0 "-"=0xAE,0xFF) so it targets 0xA40A10 (clean)
> or 0x1B2980 (patched) automatically. `combined_<code>.txt` keys are 0xA40A10.
> New CI-guard `scripts/audit_clean_base_offsets.py` flags any hard-coded offset
> whose pointer-liveness inverts between the two bases (only move_names was
> broken; DE has no move_names patch; fr item_names 0xB40FC0 is FR-only & OK).
> Full sweep in `docs/clean-base-offset-audit.md`. This closed the R-17
> follow-up B-189.

Ticket B-168/B-171 ("IT: move names + ability descriptions have zero patch
coverage") claimed move names live at `0xA40000-0xA50000` in gba_translator,
"confirmed by sampling" against `combined_it.txt`. That sampling was never
cross-checked against actual ROM bytes — it was wrong. Direct decode of
`input/roms/englishrom.gba` AND the built `GenedRom-it.gba` at that address
shows an unrelated, already-relocated Pokédex flavour-text fragment (Spinda's
dex entry), identical across every build sampled. Writing there would have
corrupted live Pokédex text without fixing anything (that address is never
read for move names).

**Method that found the real table:** encode a short, distinctive, exact
in-game string (tried "Guillotine" — a move name unlikely to be a substring
of anything else) via `src.core.text_codec.TextEncoder.encode_pokemon` and
`rom.find()` the raw bytes across the whole ROM, rather than trusting an
offset a translator/prior tool recorded. This is the generalizable technique
for future "phantom cell" tickets in this repo — the same audit methodology
(`audit_translation_collisions.py`'s "phantom" classification) that finds
`combined_it.txt` offsets with no live pointer says nothing about whether
that RECORDED offset is itself correct; always independently verify by
searching for known content before writing a patch.

Real move-name table: **0x1B2980**, stride 13, 894 entries (index 0 = "-"
placeholder, matches `src.core.moves.MOVE_COUNT`). Bafflingly, this table
holds **French** names in the pristine EN reference ROM and in every built
FR/IT/DE ROM alike — i.e. FR "works" for move names purely by accident (no
patch ever wrote it), while IT/DE currently ship French move names instead
of their own language. Fixed for IT via `languages/fr/patches/move_names.py`
(language-agnostic core) + `languages/it/patches/move_names.py` wrapper,
remapping each `combined_it.txt` entry from the wrong "legacy" offset
(0xA40A10, same stride/count, where translators historically authored this
table's text) to the real live cell. See [[unbound-ability-names-fixed-table]]
for the sibling fixed-table pattern this mirrors.

Follow-up (B-171, child tasks all landed): ability-description real table
found — `gAbilityDescriptionPointers` @ file `0x96DE04`, 293×4-byte LE
pointers, 1:1 aligned with the ability-name table (`docs/ability_descriptions_table.md`).
0xA37D00 confirmed dead the same way as the move-name address. `combined_it.txt`/
`combined_fr.txt` author **zero** ability-description text today, so the
patch itself is unblocked but has nothing to inject yet — needs a translation-
authoring pass first. The 262 overflowing IT move names were all shortened
editorially (F-104) so the full 894-entry roster now patches cleanly. DE
`move_names` wiring and the wider-contamination audit are still open.
`englishrom.gba` confirmed a French-contaminated base across move names,
descriptions, item names/descriptions, Pokédex, and species names — see
[[unbound-source-rom-french-ball-cells]] for the earlier Poké-Ball instance
of the same pattern.
