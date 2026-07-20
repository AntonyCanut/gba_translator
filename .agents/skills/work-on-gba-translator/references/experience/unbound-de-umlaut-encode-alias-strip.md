---
name: unbound-de-umlaut-encode-alias-strip
description: "DE-only bug — TextEncoder.encode(text, \"pokemon\") silently strips ü/ä/ö to ASCII unless skip_aliases=GERMAN_UMLAUT_CHARS is passed"
metadata:
  node_type: memory
  type: project
  originSessionId: 97d5b89d-d93c-4902-950f-aa0ac76aa1ab
---

Issue #53 follow-up (gba_translator, branch `unbound`, commit `2d7f7a6`): the
first pass at #53 ([[unbound-de-nature-names-official-values-fix]]) corrected
the 12 wrong *words* in `nature_names.py`'s `TARGETS` dict, but the umlauts
(`Kühn`, `Mäßig`, …) were already correct there — the bytes never reached the
ROM correctly anyway. User reopened with a screenshot proving "Kuhn" still
in-game.

**Root cause:** `src/core/text_codec.py`'s `ENCODE_ALIASES` maps `ü→u`,
`ä→a`, `ö→o` (ASCII fallback, for FR/IT/ES which have no umlaut glyphs) and
applies **by default** inside `TextEncoder.encode`/`encode_pokemon` unless the
caller explicitly passes `skip_aliases=GERMAN_UMLAUT_CHARS`. DE has real
umlaut glyphs at codepoints 0xF1-0xF6 (`GERMAN_UMLAUT_TABLE`), but only reaches
them if the alias fold is bypassed. `languages/de/patches/nature_names.py`
called `TextEncoder.encode(text, "pokemon")` with no `skip_aliases` in both
`apply()` and `verify()` — so "Kühn" silently encoded as ASCII "Kuhn" bytes,
and `verify()` "passed" because it compared against the same wrongly-aliased
expected bytes (self-consistent but wrong).

**Pattern already correct elsewhere:** `languages/de/patches/item_names.py`
and `pokedex.py` already `from src.core.text_codec import GERMAN_UMLAUT_CHARS`
and pass `skip_aliases=GERMAN_UMLAUT_CHARS` to `TextEncoder.encode_pokemon`.

**How to apply:** any DE patch script that calls `TextEncoder.encode(...,
"pokemon")` or `encode_pokemon(...)` on a string that may contain ä/ö/ü/Ä/Ö/Ü
MUST pass `skip_aliases=GERMAN_UMLAUT_CHARS`, or umlauts silently become
their ASCII fallback (no exception, no visible failure — verify() will even
report clean if it uses the same un-fixed encode call). When auditing a DE
umlaut report, grep `languages/de/patches/*.py` for
`TextEncoder.encode(...pokemon...)` / `encode_pokemon(` calls missing
`skip_aliases`, don't just check the source-of-truth word list.

**Verification method used:** rebuilt the full DE ROM (`make build-de`) and
read the byte at the live pointer-table offset directly (0x463E60, table
index = nature index), rather than trusting `verify()`'s own printed
"clean" status — see [[unbound-de-nature-names-table-driven-patch]] for why
whole-ROM substring search / self-referential verify can give false
positives.
