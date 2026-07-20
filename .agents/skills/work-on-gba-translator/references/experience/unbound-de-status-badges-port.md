---
name: unbound-de-status-badges-port
description: DE status badge LZ77 tiles port (GIF/SCH/GEF/VBR/KO) + generic status_badges dispatch step
metadata:
  node_type: memory
  type: project
  originSessionId: 0770eabf-eb63-4452-a20c-a2d8b7d6c107
---

Ported the FR in-battle **status badge** LZ77 tile patch to German (P-86 slice).
Distinct from the text `status_abbrevs` table (see [[unbound-status-abbrev-sommeil]]) —
badges are 4bpp LZ77 tile graphics, one dedicated `_de.py` per language.

- `scripts/patch_status_badges_de.py` mirrors `_fr.py`: same 4 BADGE_BLOCKS, same
  8-slot layout. DE mapping by fixed engine slot: 0 PSN→GIF, 2 SLP→SCH, 3 FRZ→GEF,
  4 BRN→VBR, 6 FNT→KO. Slot 1 (PAR) unchanged. New glyphs designed: I F C H V (reused B E G R S O K from FR).
- Wired a **generic** `status_badges` step into `build_language.py` via
  `_status_badges_script_for(code)` (resolves `patch_status_badges_<code>.py`, falls
  back to FR) — same pattern as `_font_script_for`. Added `status_badges` to
  `languages/de/lang.yaml` patches list (after `status_abbrevs`, before `version`).
- Tests: `tests/test_patch_status_badges_de.py` (pixel round-trip + registry sync
  guard) and a dispatch test in `test_generic_build_patches.py`.

**How to apply:** the 3 remaining P-86 graphical DE patches (type_icons, hp_labels→KP,
dexnav_headers) follow the same recipe: dedicated `_de.py`, `_<name>_script_for(code)`
resolver in build_language, add step to de/lang.yaml, mirror the FR test.
Run pytest via `rtk proxy python3 -m pytest` (bare pytest fails under the rtk hook).
