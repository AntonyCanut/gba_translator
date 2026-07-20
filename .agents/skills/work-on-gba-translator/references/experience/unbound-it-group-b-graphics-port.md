---
name: unbound-it-group-b-graphics-port
description: "IT group-B graphics port (type_icons, status_badges, dexnav_headers) + hp_labels decision (F-95→F-97)"
metadata:
  node_type: memory
  type: project
  originSessionId: 8b3b38fb-8984-4c75-b117-e5056105b061
---

Ported the FR/DE graphics/tile patches (group B) to Italian in gba_translator
(branch `unbound`). All are baked 4bpp tiles in LZ77 blocks — the text pipeline
never reaches them, so each ships a per-language glyph set. See also
[[unbound-de-status-badges-port]], [[unbound-multilang-build-registry]].

- **type_icons** (`patch_type_icons_it.py`): LOTTA/VOLANTE/TERRA/ACQUA/… across
  both sheet copies (0xB1EC64 summary, 0x961A00 battle). Added the **Q** glyph
  (ACQUA); every name ≤32px pill. Reuses DE's _FONT base set.
- **status_badges** (`patch_status_badges_it.py`): slots 0/2/3/4 → PSN/SON/CON/SCT
  + slot 6 KO; slot 1 PAR unchanged. Added glyphs **P/N/O/T** (C/S already in the
  shared badge font). Must match `languages/it/lang.yaml` status_abbrev.
- **dexnav_headers** (`patch_dexnav_headers_it.py`): LIVELLO RIC / METODO /
  ABILITA NASCOSTA / OGGETTI. Added **G** glyph (OGGETTI). The FR `known_good`
  English tile fingerprints match the IT ROM verbatim (same base asset) — copied
  as-is. Recompressed tileset must stay ≤ original comp len (tilemap follows w/
  zero gap).

Wired the 3 steps into `languages/it/lang.yaml` (after status_abbrevs). Dispatch
in `build_language.py` was already generic (`patch_<name>_<code>.py` resolution;
status_badges falls back to FR). dexnav_headers dispatch landed concurrently via
a DE ticket — do NOT re-add it (rebase brings it in).

**hp_labels (F-97 RESOLVED — was NOT ported by F-95).** F-95's analysis decoded
the 3 HP-label blocks in GenedRom-it.gba: party menu 0x008001D0 = EN «HP»,
summary bar 0x00E9B4B8 = ES «PS» (only this one fixed by repair_localized_lz77),
grey stat 0x00E9A460 = EN «HP» → 2/3 still English. That finding motivated the
dependent ticket **F-97**, which LANDED a dedicated `scripts/patch_hp_labels_it.py`
stamping «PS» across all 3 blocks. **Final `unbound` state (commit 40c4fa5):** all
4 graphics steps wired in `languages/it/lang.yaml` in order
`status_badges → type_icons → hp_labels → dexnav_headers`. The interim
`docs/it_hp_labels_decision.md` ("do not port") was DROPPED during integration —
do NOT recreate it; hp_labels IS ported now.

**Integration was messy (zombie-complete + repeated base advance).** F-95's
`orchestration_complete` was accepted but the ticket lingered "working"; the
worktree was deleted and recreated at a much newer `unbound` HEAD, and my commits
were folded into `40c4fa5 feat(it): port graphics and pokédex patches from FR/DE`.
Lesson (cf. [[singularity-zombie-run-stale-complete]]): verify the LIVE branch
(`git cat-file -e unbound:scripts/...`, inspect lang.yaml) before re-doing or
re-completing — the work was already there. Rebasing my old commits produced a
lang.yaml conflict (my 3 steps vs F-97's hp_labels) that resolves to keep all 4.

**Post-merge gotcha (2026-07-03):** a concurrent version fix made
`build_language.py` read `config.version_label` in the `version` dispatch branch.
The `_FakeConfig` in `tests/test_generic_build_patches.py` lacked it → 3 dispatch
tests `AttributeError` after a clean rebase. Fix = give the fake
`version_label = config.version_label`. Classic clean-rebase-but-broken case; the
`orchestration_pull` post-merge re-test caught it.

**How to verify graphics offsets without a full rebuild:** copy the existing
`output/roms/GenedRom-it.gba` to /tmp and run each `patch_*_it.py --rom` on it —
confirms blocks/offsets match the real IT build and idempotency (re-run =
byte-identical / dexnav skips "not known English art"). Run tests via
`rtk proxy python3 -m pytest` (bare pytest fails under the rtk hook).
