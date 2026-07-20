---
name: unbound-collision-audit-tool
description: Language-agnostic inter-cell collision detector for DE/IT/FR builds — source-terminator gate is the precise discriminator
metadata:
  node_type: memory
  type: reference
  originSessionId: 30ec3000-183f-457c-8ff7-3711682c89a3
---

`gba_translator/scripts/audit_translation_collisions.py` + `src/core/collision_check.py`
audit a built ROM for translated strings not terminated (0xFF) before the next
live cell (fusion / freeze risk in packed description tables). Also runs as a
report-only `collision_check` post-build step (in `build_language.py`, in the
DE and IT `lang.yaml` patches).

**The precise discriminator (avoids false positives):** an overrun is a real
collision only when the ENGLISH source had a 0xFF boundary in the gap that the
build destroyed. When the source is *also* unterminated across the gap, the
`next_offset` is just an interior fragment of one long string that combined_*.txt
happens to list — NOT a real cell boundary. `next_is_live` (neighbour is
pointer-addressed) is secondary corroboration. Relocated cells (live pointer no
longer targets the offset) are dead in place → never flagged.

**Confirmed findings (2026-07-03):** DE combined batches 1-4 = 90 real collisions
(40 fuse a live neighbour); IT = 771.

**FIXED B-154 (2026-07-03) — root-cause collision guard, both DE & IT → 0 confirmed.**
The generic DE/IT build has TWO in-place writers, both had to be guarded:
`19_build_translated_rom_generic.py` (via SmartReinserter) writes MOST text, and
`scripts/apply_inline_overrides_fr.py` writes the rest. Root cause: the padding
heuristic counts the 0x00/0xFF run after a terminator, which spills into the next
packed cell, so a verbose translation overran. Guard = opt-in `--collision-guard`
(OFF for FR so `make build-fr` stays byte-perfect): cap each in-place write so its
terminator lands strictly before the next occupied cell (`offset+encoded_len <
next_offset`); too-long entries then relocate (translation preserved) instead of
overrunning. Boundary set = combined∪English∪Spanish cell starts; pass the whole
`combined_<code>.txt` to 19_build via `--extra-boundaries` so scanned PHANTOM
offsets (empty in EN, no live pointer) also count as walls. Last 3 IT residuals
were relocated strings legitimately reusing free space that spans phantom offsets
→ refined `collision_check` to skip when `source_rom[offset]==0xFF` (empty source
cell = free space, not a destroyed boundary). Also fixed the pre-existing DE
`patch_font_de.py` "Not enough free space" blocker: ported the whole-ROM 0xFF-run
`FreeSpaceAllocator` from `patch_font_fr.py` (was trailing-only; reinserter
relocations had eaten the tail). See also
[[unbound-nopointer-inplace-budget]] (phantom/no-pointer cells), [[unbound-move-descriptions]]
(FR re-wrap+relocate pattern), [[diagnosing-unbound-freezes-skill]],
[[unbound-build-determinism-relocation-order]] (guard is order-independent → deterministic).

Run: `python3 scripts/audit_translation_collisions.py --combined languages/<c>/combined_<c>.txt --rom output/roms/GenedRom-<c>.gba --english input/roms/englishrom.gba --json r.json [--fail-on-collision]`.
