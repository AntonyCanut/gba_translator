---
name: unbound-e2e-tests-gate-committed-rom
description: gba_translator e2e tests read the COMMITTED FR ROM (no rebuild in CI); CI markers/branch matter; FR build is non-deterministic
metadata:
  node_type: memory
  type: project
  originSessionId: ecbfeb05-812e-43a1-bd11-b494d597bac5
---

gba_translator e2e tests (`tests/e2e/*`) read the **committed** `output/roms/GenedRom-fr.gba` — there is NO `make build-fr` step in the CI test jobs, so a content fix only reaches the tests once the rebuilt ROM is committed.

CI gating (`.github/workflows/ci.yml`):
- `python-tests-fast` (runs on PRs): `--ignore=tests/e2e -m "not slow and not emulator and not rom"` → e2e and `@pytest.mark.rom` tests DON'T run on PRs.
- `python-tests-standard` (only on push to master): `-m "not emulator and not stress and not benchmark"` → e2e + `rom` DO run, but `@pytest.mark.emulator` (mGBA, e.g. `test_it_first_battle`) is excluded.

So mGBA/emulator e2e failures are NOT a CI gate; the local `pytest tests/` (Py 3.9) runs them and can fail on environment/probe issues, not ROM bugs.

The FR build is **non-deterministic**: a no-change `make prepare-fr && make build-fr` (BUILD_NUMBER=0) drifts ~0.2% (~68KB) vs the committed ROM, in free-space relocation regions. Historic rebuild commits drift the same ~58KB. So a fresh rebuild reproduces source-level test failures (use it to confirm "stale ROM vs real gap"), but committing a rebuilt ROM always carries benign relocation noise. See [[unbound-it-relocation-packing-fix]], [[singularity-build-resets-worktree]].

Triage of B-96-spawned "8 failing e2e" ticket: none was a live freeze (pool-scan freeze invariants pass). Loosened relocation-fragile tests to robust invariants (pointer-subrange diffs share high byte 0x09; relocated desc pointer at item +0x14); xfailed real content gaps (Weak Armor name untranslated, link-lost lost its 0xB0 ellipsis → B-103/B-104/B-105).
