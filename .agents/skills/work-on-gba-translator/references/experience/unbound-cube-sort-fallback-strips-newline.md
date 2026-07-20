---
name: unbound-cube-sort-fallback-strips-newline
description: "An in-budget combined_fr.txt translation at a no-pointer offset can still get corrupted by the injector's --allow-fallback synthesis, which drops manual \\n control codes"
metadata:
  node_type: memory
  type: project
  originSessionId: 80d232f5-d1f0-4742-87ac-9a35ba52f5a0
---

Issue #76 (regression on top of [[unbound-cube-sort-menu-no-pointer-silent-drop]], #25):
the Cube "Sort this pocket's items how?" prompt (0xA4E047) has no live pointer, so the
main injector (`src/translators/19_build_translated_rom_generic.py`, invoked with
`--allow-fallback`) cannot relocate a French replacement there. The prior assumption
(from #25) was "no pointer → pipeline silently skips → leaves EN original → the
dedicated `languages/fr/patches/cube_sort_menu.py` class-3 patch safely overwrites it".

**That assumption only holds when the `combined_fr.txt` translation is long enough to
be rejected outright.** If the translation instead *fits* the EN byte budget (even
comfortably), `--allow-fallback` does NOT skip it — it synthesizes an in-place FR
variant, but that synthesis **drops the manual `\n` (0xFE) escape** and writes the
text as a single unbroken line. The renderer then overflows the fixed-width popup box
and truncates mid-word — reproducing almost exactly the kind of garbled text a user
would report as "translation is wrong" (e.g. "Comment trier les ob," / "poche ?").

Worse: once the fallback has written *something* non-EN at that offset, the class-3
patch's safety check (`current bytes == expected EN original, else WARN+skip`)
correctly refuses to overwrite unknown content — so the class-3 fix silently stops
applying too. Both fixes cancel out and the corrupted fallback text ships.

**Why:** the old `combined_fr.txt` entry for this offset ("Comment trier les objets
de\ncette poche ?", ~43 bytes) happened to exceed the ~30-byte slot, so it was
harmlessly rejected — this was accidental safety, not a documented invariant. A
"cleanup" that shortens the translation to fit (e.g. to better match EN/ES wording)
silently re-enables the fallback-synthesis bug.

**How to apply:** for any no-pointer/no-live-pointer offset owned by a dedicated
class-3 patch script, do NOT add or shorten a `combined_fr.txt` entry to "just barely
fit" the byte budget — leave the offset **absent** from `combined_fr.txt` entirely
(with an explanatory `#` comment) so the injector never touches it at all, and the
class-3 patch remains the sole, uncontested owner. Verify by grepping the offset out
of the generated `output/translation/*_translation_ready.json` before rebuilding, and
by checking `make build-fr`'s patch output for `WARN 0x<offset>: expected EN
original... skip` (a WARN there means something upstream wrote non-EN bytes first —
investigate before assuming the class-3 patch fixed anything).

See also [[unbound-trace-live-pointer-not-original-offset]],
[[unbound-nopointer-inplace-budget]].
