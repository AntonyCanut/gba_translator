---
name: unbound-generic-build-blanket-spanish-reservation-overreserves
description: "REVERTED: #54's precise inline-span reservation broke CI (build-de/build-it exit 1). The blanket Spanish carve is REQUIRED — do NOT reintroduce reserve-ranges."
metadata:
  node_type: memory
  type: project
  originSessionId: 76638c63-0daa-4055-ae6e-2b1518c5d156
---

Generic (DE/IT/indie) builds relocate over-long translations into English 0xFF free space. `flush_relocations` reserved the ENTIRE Spanish ROM footprint (`reserved_rom=pointer_proof_rom`) so relocated text couldn't be clobbered by the post-build `inline` step (`apply_inline_overrides_fr.py`, run for every lang whose `lang.yaml` `patches` includes `inline`).

**Key insight (B, issue #54 follow-up):** that blanket carve is wildly over-conservative. The inline pass writes IN-PLACE only at `combined_<lang>.txt` offsets that also exist in the Spanish extraction — for DE only ~11 of those spans (901 bytes) actually overlap the free-space pool. Every OTHER Spanish-occupied free byte is a proven-safe relocation target (Spanish itself relocated text there and shipped a working ROM). Reserving only the real inline-write spans reclaims **~32KB**.

**Fix shipped (commit 0d89a68 on branch unbound):**
- `apply_inline_overrides_fr.py --dump-write-ranges` = dry run emitting exact `(offset,len)` spans; content-derived so a dry run on englishrom == the real writes on the built ROM (verified 6633==6633).
- `FreeSpaceAllocator(reserved_ranges=...)` carves those spans from the finished block list (sorted sweep — do NOT loop ranges per-0xFF-run, that's O(runs×ranges) and times out).
- `19_build --reserve-ranges` prefers ranges over blanket `--pointer-proof-rom` carve.
- `build_language.py` dry-runs inline pre-build, passes the ranges.

**Result:** clean `make build-de` relocation_failed **195→103**. FR path untouched/byte-identical (no `--reserve-ranges`).

## ⚠️ REVERTED — #54 broke the release pipeline (2026-07-07)

The precise-reservation premise was **incomplete**: the blanket Spanish carve does NOT only protect the inline mirror pass. It also (implicitly) **preserves the EN-free / ES-populated pool that the POST-BUILD relocation harvesters consume** — `languages/de/patches/mission_descriptions.py` (47 bounty descs, harvests with `reference_rom=False`/`reserved=None`), `worldmap_junction_panels.py`, and IT `scripts/patch_long_dialogues_it.py`. Those patches run at the END of the patch list and deliberately relocate into the ~29KB pool the main pass used to avoid. After #54 the main pass ate that pool, so the harvesters found **no free space**, and each `main()` returns 1 on `stats['failed']>0` → `make build-de` / `build-it` exit 1. Run #43 of "Build & Release ROMs" failed on Build German ROM, Build Italian ROM, and the "Fail if Italian ROM was not delivered" publish gate. **FR was unaffected** (blanket carve retained on the FR path). Free space is a genuine hard budget ("the Italian build's relocation demand exceeds the total free space").

**Fix = `git revert 0d89a68`** (restores blanket carve) + regression test `tests/test_reinserter_relocation.py::PostBuildHarvesterPoolTests` asserting the main pass never allocates into the reference-populated pool and a `reserved_rom=None` harvester can still relocate there. Verified: `make build-de` → mission descriptions 47/47 relocated; `make build-it` → long_dialogues 5/5 relocated; both exit 0.

**Rule: do NOT reintroduce `--reserve-ranges` / precise inline-span reservation** unless the post-build harvesters (`mission_descriptions`, `worldmap_junction_panels`, `long_dialogues_it`) are first taught to reserve their own footprint up front, or made non-fatal. The +32KB "win" ships nothing if the build fails. See [[unbound-generic-build-freespace-blocks-relocation-patches]], [[unbound-multilang-build-registry]], [[unbound-fr-build-lives-in-gba-translator]].
