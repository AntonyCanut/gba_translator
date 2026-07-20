---
name: unbound-dresco-trainer-house-signboard-pagebreak-split
description: World-map info-panel sign text mis-split across the page-break control code (issue
metadata:
  node_type: memory
  type: project
  originSessionId: 51332994-6ba0-4daa-8df1-6b85632323a1
---

Fixed offset `0x1F70B84` in `combined_fr.txt`: was `Maison des\pDresseurs Combattez à volonté !` (page-break `\p` landing mid-title), corrected to `Maison des Dresseurs\pCombattez à volonté !`.

**Why:** these world-map popup strings (Route/Town/Gym/House names near 0x1F70xxx) follow an EN pattern of `<Title>\p<Description>` — title on screen 1, description on screen 2. EN source confirmed via `output/extracted/extracted_texts/englishrom_texts.json`: `"Trainer House<0xFB>Battle to your heart's content!"`. The FR translator had put the `\p` one word too early, splitting the title itself across the two screens.

**How to apply:** for any "wrong timing" / "text cut at the wrong place" bug report on a town/building/landmark sign, decode the EN source at the same offset first — the correct split point is wherever EN puts its own `\p` (0xFB), not wherever it looks natural in French. This particular fix was byte-length-neutral (same total chars, `\p` just moved across a word boundary), so no relocation was needed — verify with a decode of the rebuilt ROM at the same offset, not just the source file.

Also hit a rebase conflict here: base branch had a concurrent gym-leader rename (Mirskle→Sylvain) touching an adjacent line in the same file/table. Per [[unbound-rom-rebase-conflict-rebuild-resolution]], resolved by keeping both text edits in `combined_fr.txt` then rebuilding the ROM from the merged file (never pick ours/theirs on the binary `output/roms/GenedRom-fr.gba`).

Also: running the gba_translator pytest suite invokes `tests/unit/test_sync_charmap.py`, which actively regenerates `emulator-web/src/charmap.ts` and `tests/e2e-playwright/helpers/charmap.ts` from `src/text/charmap_data.py` as a side effect (not just `--check`). If those two files show as modified after a test run and the diff is unrelated to your ticket, `git restore` them before committing/pulling — don't accidentally commit unrelated charmap drift.
