---
name: unbound-worktree-generic-build-artifact-reuse
description: "Speed up build_language.py it/de inside a Singularity worktree by symlinking the main checkout's gitignored extraction/diff artifacts"
metadata:
  node_type: memory
  type: project
  originSessionId: a5c6f2c3-2056-4b7b-8784-7e673d4191b4
---

`scripts/build_language.py <code>` (generic IT/DE builder in gba_translator) needs
heavy artifacts that are gitignored and therefore ABSENT in a fresh Singularity
worktree, forcing a slow ~minutes 32MB `--scan-all-pointers` re-extraction.

Reuse the main checkout's copies instead (all under `output/`, gitignored, so
symlinks never dirty git):

- `output/extracted/extracted_texts/englishrom_texts.json` + `spanishrom_texts.json` (233MB each) → `ensure_extractions()`
- `output/differences/pointer_{text_differences,translation_pairs,offset_map}.json` → diff step
- Base CSV: post the B-160 refactor the builder generates `output/translation/generic_base_trilingual.csv` itself from the EN extraction (no `--french`); older code globbed `*_trilingual_translation.csv` (pick newest). Don't hand-feed a per-language `it_trilingual_translation.csv` as the base — it's overwritten anyway.

Then `python3 scripts/build_language.py it --build-number N` runs in a few min.
macOS has no `timeout`; run in background + poll the log. `pytest` must be
invoked as `rtk proxy <python> -m pytest` (the rtk hook mis-intercepts even
`<python> -m pytest`, failing with "No such file or directory").

GOTCHA: symlink `output/extracted` + `output/differences` freely, but NOT the
whole `output/translation` dir — it holds git-TRACKED files (`french_texts.json`,
`french_template.json`, `demo_french_texts.json`); replacing the dir with a
symlink shows them as `D` in git. Either symlink only the specific gitignored
files you need (`it_translation_ready.json`, `generic_base_trilingual.csv`), or
after building `rm` the symlinks (links only — never `rm -rf`, which deletes the
main checkout's targets) and `git checkout -- output/` to restore tracked files.

See [[unbound-fr-build-lives-in-gba-translator]], [[unbound-multilang-build-registry]],
[[unbound-generic-build-freespace-blocks-relocation-patches]].
