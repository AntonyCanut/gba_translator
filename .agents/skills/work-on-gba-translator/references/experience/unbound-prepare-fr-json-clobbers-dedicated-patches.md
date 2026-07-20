---
name: unbound-prepare-fr-json-clobbers-dedicated-patches
description: prepare_fr_json (CI FR JSON generator) emits arrow-prefixed junction offsets as too_long → generic builder re-wraps them → patch_worldmap_junction_panels_fr verify fails build-fr
metadata:
  node_type: memory
  type: project
  originSessionId: 34b58dc2-810f-45f8-8ca5-65ef17ef8b86
---

CI `make build-fr` (gba_translator branch `unbound`) builds the FR translation JSON via `scripts/prepare_fr_json.py` (from combined_fr.txt + EN extraction, commit 16d7fcb). That generator iterates ALL combined_fr offsets — including the arrow-prefixed World-Map junction panels (0x1F726C0 etc.), which the extractor sees as 1-byte arrow strings (original_length=1). So they go out as `too_long=True`, and the generic builder (`--allow-relocate`) relocates AND re-wraps them, destroying the arrow-at-line-start layout + contiguous comma-fragments that `patch_worldmap_junction_panels_fr.py` verifies → build fails: `0x01F726C0/0x01F72735/0x01F727D0: French fragment not found in ROM` (the 3 multi-fragment panels), with the patch reporting `Already relocated (skip): 9`.

**Fix (commit 25b8e74):** `prepare_fr_json.py` now excludes `DEDICATED_PATCH_OFFSETS` (imported from the junction patch's `TARGETS`, fallback hardcoded) from BOTH the normal loop and the --english-rom fallback. The EN original stays in place → the dedicated byte-exact patch relocates verbatim → verify passes.

**Why:** any offset owned by a dedicated post-build patch must NOT also be in the generic translation JSON, or the generic relocator clobbers it.

**How to apply:** when a new dedicated post-build patch claims offsets that ALSO exist in combined_fr.txt, add them to `DEDICATED_PATCH_OFFSETS` in prepare_fr_json (or import the patch's TARGETS). `skip=N (Already relocated)` + `fragment not found` in a relocation patch = the generic builder got there first.

**Trap:** a previous run misdiagnosed build #3's failure as the final pytest guard (`test_location_names_fr.py`); the CI log showed build #3 actually died at the SAME junction patch. Always read `gh run view <id> --log-failed`, never trust a narrative of where it failed. Related: [[unbound-worldmap-junction-panels]] [[unbound-arrow-line-start-audit]].

**Follow-on (commit f1d71ce):** once the junction patch stopped aborting, the build reached the `test_location_names_fr.py` guard and exposed 3 more spots where the CI `prepare_fr_json` path is weaker than the dev's uncommitted rich-CSV golden ROM (the regression tests pass on the committed golden but fail on every CI rebuild): (1) 0xB500A0 "Bourg Gurun" — prepare_fr_json measured the bare EN string as the slot, marked it too_long, generic relocator truncated the leading byte → "ourg Gurun"; (2) 0xB535C8 "Île de la Lune" — fits but a later restore pass left English; (3) 0x1F49B76 Dresco-Town NPC line — absent from combined_fr.txt entirely (lived only in the CSV). Fix: new `patch_worldmap_labels_fr.py` writes the 2 labels in-place (bounded by EN slot + trailing 0x00/0xFF padding run) run LATE after all EN-restore passes; + add the missing 0x1F49B76 line to combined_fr.txt so the pipeline relocates+repoints it. Key debugging unlock: the ROMs ARE committed at `input/roms/englishrom.gba` + `spanishrom.gba` + golden `output/roms/GenedRom-fr.gba`, so you CAN build locally (`make prepare-fr && make build-fr`) and diff golden-vs-CI-rebuild — don't assume "no ROMs locally".

**IT build (separate, child ticket of B-84):** the same CI workflow also runs `make build-it`, which crashed with `ModuleNotFoundError: No module named 'yaml'` — pyyaml (the registry's only dep, per CLAUDE.md) was undeclared in pyproject.toml `dependencies=[]`, so CI's clean `pip install -e .[dev]` lacked it (works locally only because yaml is globally installed). Fix = `dependencies=["pyyaml>=6.0"]`. The IT step is `continue-on-error` but a final guard step `exit 1`s the job when IT isn't delivered, so the whole CI stays red until IT builds.

**Shared-worktree race:** the gba_translator main worktree is shared across concurrent Singularity tasks — files (pyproject.toml, new test files, the rebuilt ROM) appeared mid-task from a sibling agent. Don't commit another task's in-flight edits; scope `git add` to your own files.
