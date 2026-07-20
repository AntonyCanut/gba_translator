---
name: unbound-stat-change-baked-verb-b35-not-pure-buffer
description: Battle stat-change templates 0x3FCB5F/6A/8F/9A must BAKE the verb (augmente/baisse); pure-buffer form is a stale-test trap
metadata:
  node_type: memory
  type: project
  originSessionId: 9966b1c6-2c0c-4cd0-8670-c4efdcb1e2e0
---

Battle stat-change messages ("Stat de Nom\naugmente beaucoup !") at combined_fr
offsets 0x3FCB5F/0x3FCB6A (rise) and 0x3FCB8F/0x3FCB9A (fall) must keep the
conjugated verb BAKED into the template before `<0xFD><0x01>`, with modifier
0x3FCB41/0x3FCB50 = `beaucoup<0x00>` and verb buffers 0x3FCB4A/0x3FCB59 = `!`.

**Why:** the engine builds the intensity buffer `<0xFD><0x01>` as `modifier+verb`
and ALWAYS prepends the modifier. A pure-buffer template (`…\n<0xFD><0x01>`,
verb in buffer) renders the ungrammatical "beaucoup augmente !". Ticket **B-35**
(commits 28573962 / 3050eef) fixed this; locked by `tests/test_battle_stat_change_order_fr.py`
(pre-commit fast suite).

**How to apply:** do NOT "fix" these to pure-buffer / "fortement " even though an
older e2e test (`test_nodulithe_passive_fr.py::TestWeakArmorActivationMessage`)
once asserted that — that test was STALE (skipped, never validated) and was
aligned to B-35 in B-121. Reverting combined_fr.txt to pure-buffer reintroduces
the grammar bug AND breaks the B-35 unit suite (commit becomes impossible).

Also (B-121): the e2e gba_translator aggregate tests had false-positive logic —
FD-preservation compares EN raw `<0xFD>` vs FR semantic `{braces}` (same codes,
build expands braces→FD bytes positionally, ~93% real); the null-run check flags
legitimate trailing space-padding (0x00 = space); the longest-entries match
sampled never-injected entries. See [[combined-fr-duplicate-offsets-last-wins]],
[[unbound-battle-stat-change-effect-text]], [[unbound-mega-cuff-reaction-strings]].
