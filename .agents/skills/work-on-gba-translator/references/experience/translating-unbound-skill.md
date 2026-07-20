---
name: translating-unbound-skill
description: A Claude skill documents the full EN→FR translate+apply+verify workflow for Pokemon Unbound
metadata:
  node_type: memory
  type: reference
  originSessionId: 0433ab90-c089-44c3-90f2-228b17bbb8e1
---

The translate-and-apply workflow is captured as a Claude skill at
`Test/Unbound/.claude/skills/translating-unbound/SKILL.md` (version-controlled via a
`.gitignore` exception: `.claude/*` ignored but `!.claude/skills/` kept). Invoke it before
any FR text correction.

It covers: translations live in [[unbound-fr-build-lives-in-gba-translator]] (not this
toolkit); the build chain (`apply_combined_fr.py --extend` → `09_csv_to_json_v2.py
--allow-too-long` → `make build-fr`); the two text classes (pointer-based vs fixed-width
name cells — see [[unbound-pipeline-unreachable-name-cells]] and
[[combined-fr-duplicate-offsets-last-wins]]); the Town Map→Carte case study; and
verifying decoded ROM bytes instead of screenshots.
