---
name: unbound-pc-trade-link-cable-overflow
description: "PC trade counter \"battle another Trainer via Link Cable\" text overflowed the message box (issue"
metadata:
  node_type: memory
  type: project
  originSessionId: 541e7504-c522-4cc3-adff-04e2fd6ae010
---

Offset `0x1BC3C7` in `combined_fr.txt` ("Tu peux combattre un autre Dresseur\nvia un câble Game Link GBA.") had a first line 200px wide against the 192px `DEFAULT_MAX_LINE_WIDTH` budget in `src/core/dialogue_linewrap.py` — box overflow, dialogue couldn't advance. Fixed to "Tu peux combattre un autre\nDresseur via un câble Link." (150px/149px), matching the reporter's suggested wording. Same offset family: `0x1BC388` (Échange…) is also borderline over budget (194px) but wasn't touched — fixing it needs a wording shorten, not just a rewrap, and wasn't part of this report.

**Why:** GitHub issue #19 (gba_translator) — screenshot showed the sentence couldn't be scrolled past. `src/core/dialogue_linewrap.py`'s `line_widths()`/`rewrap()` gives an exact pixel budget check and a clean re-flow when a `\n` already exists in the string.

**How to apply:** For "text can't advance / overflows box" reports, decode the sentence and run it through `dialogue_linewrap.line_widths()` before guessing wording — confirms the real cause (pixel overflow vs. something else) and `rewrap()` gives a balanced 2-line split for free. See [[translating-unbound-skill]] for the build chain (`make prepare-fr` + `make build-fr` when no trilingual CSV is committed).
