---
name: unbound-normalize-multiline-comment-swallow-bug
description: "normalize_combined_multiline.py bug: a comment right after an entry (no blank-line flush) got swallowed into that entry's text — fixed in B-165"
metadata:
  node_type: memory
  type: project
  originSessionId: 51e2515c-4bcc-4791-89b9-5c36f0b5299e
---

`scripts/normalize_combined_multiline.py` (gba_translator) folds multi-line
`combined_<code>.txt` entries into single lines with literal `\n` escapes.
Its first version only treated a `#` comment line as "standalone" when
`pending is None`; a comment immediately following an entry (separated only
by a blank line, no offset line yet to flush `pending`) was appended as
**continuation text** into the *previous* entry instead of staying a comment
— e.g. `0xf8f4f7: ik<0xFC><0x77>` absorbed the whole
"# Item & TM/move descriptions inherited FRENCH..." block as literal
`\n#...` text, which would have injected the comment into the built ROM.

Fix: a comment line must always `flush()` any pending entry first, regardless
of whether `pending is None`. Found only by empirically rebuilding
`GenedRom-it.gba` pre/post-normalization and decoding entries via their
**live pointers** (not raw offsets — best-fit relocation can move an entry
elsewhere, e.g. item 62's Poké Ball description moved from `0x7b3bea` to
`0xc5cf28` once its text was no longer truncated) — the unit test alone
(`test_normalizer_is_idempotent_and_lossless`) did not catch it, since it
only checks the fold count, not content correctness.

Also confirmed: normalizing 165 truncated entries to their full length
cascades into ~640KB / 205 regions of raw ROM-byte diff across the whole
build, because free-space packing is best-fit and order/size-sensitive (see
[[unbound-it-relocation-packing-fix]], [[unbound-build-determinism-relocation-order]]).
A large raw `cmp` diff after this kind of fix is *expected*, not a red flag —
verify via decoded live-pointer text + the `-m rom` pytest suite instead of
`cmp -s`.

If DE or another language ever needs this normalizer, re-check for the same
class of bug pattern if the script is forked/copied instead of reused.

See [[unbound-fr-build-lives-in-gba-translator]], [[unbound-multilang-build-registry]].
