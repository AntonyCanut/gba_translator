---
name: unbound-fr-build-csv-symlink-writeback-hazard
description: "gba_translator FR build chain: symlinking output/translation/*.csv from the main checkout into a worktree is dangerous because apply_combined_fr.py and 09_csv_to_json_v2.py WRITE to that path in place"
metadata:
  node_type: memory
  type: project
  originSessionId: 99a9e257-8e60-4b3a-a43d-e6004c9597ba
---

When speeding up a Singularity-worktree FR build by reusing the main checkout's
gitignored `output/` artifacts (see [[unbound-worktree-generic-build-artifact-reuse]],
which covers IT/DE `build_language.py`), the FR chain (`apply_combined_fr.py --extend`
→ `09_csv_to_json_v2.py`) is different: its default CSV
(`output/translation/2026-01-15_trilingual_translation.csv`) is not a pure read
input — `apply_combined_fr.py` opens it and **writes the updated CSV back to the
same path**. Symlinking it from the main checkout means the write goes straight
through to the shared file, mutating the main checkout's build artifact from
inside a worktree (a real risk with concurrent tickets also running FR builds).

**Fix:** for `output/translation/*.csv`, `cat` the main-checkout file into a temp
file, `rm` the symlink, then `mv` the temp file into place — this materializes a
real worktree-local copy before the first write. Only symlink files that are
purely read-only for this chain: `output/extracted/extracted_texts/{english,spanish}rom_texts.json`
and `output/differences/pointer_{offset_map,text_differences,translation_pairs}.json`
(deterministic, derived from static input ROMs, safe to share). `patchedfrenchrom_texts.json`
gets regenerated fresh by `make build-fr` itself every run — don't symlink it either,
just let the build recreate it locally.

Also: after a `git rebase` lands new commits from a concurrent ticket, the
worktree-local CSV/JSON go stale — rerun `apply_combined_fr.py --extend` and
`09_csv_to_json_v2.py` again before `make build-fr`, don't reuse the pre-rebase
generated JSON.

See also [[unbound-fr-build-lives-in-gba-translator]], [[translating-unbound-skill]].
