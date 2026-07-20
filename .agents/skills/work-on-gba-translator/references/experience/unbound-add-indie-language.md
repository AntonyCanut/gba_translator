---
name: unbound-add-indie-language
description: How a new translation language (e.g. Indie) is added to the gba_translator multilang registry
metadata:
  node_type: memory
  type: project
  originSessionId: 22514af8-e05b-4d8f-863d-c7dcb4e00351
---

Adding a new generic translation language to gba_translator (branch `unbound`) is
purely declarative — mirror the IT/DE pattern, no builder code changes:

1. `languages/<code>/lang.yaml` (build: generic, status: in_progress) — code MUST
   equal folder name; required keys incl. builder_language, output_rom, version_label,
   and a full status_abbrev (poison/burn/freeze/paralysis/sleep/faint).
2. `languages/<code>/combined_<code>.txt` (format `<offset_hex>: <text>`); absent
   offsets stay English so a near-empty seed still boots.
3. Makefile: `build-<code>` target + add to `build-all` + help. `build-lang LANG_CODE`
   and `release-all`/package_release already iterate the registry automatically.
4. `tests/test_language_registry.py`: add code to EXPECTED_BUILDABLE + the
   GENERIC_CODES parametrize list.

Reusing the FR font needs NO patch_font_<code>.py — `_font_script_for()` in
build_language.py falls back to patch_font_fr.py. The `version` patch renders
`<CODE>.2.1.<build>` glyphs; long codes (e.g. INDIE) clip but don't crash.
Full ROM build is heavy + gitignored → validated in CI, registry+fast tests
(`rtk proxy python3 -m pytest tests/`) green locally is the local bar. See
[[unbound-multilang-build-registry]] and [[unbound-fr-build-lives-in-gba-translator]].
Done in ticket "Traductions Indie" (commit 1e1563c).
