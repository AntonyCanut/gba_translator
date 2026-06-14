---
name: brainstorming
description: Use before any new feature, pipeline change, or architectural decision — explores intent and design before implementation
when_to_use: New features, pipeline additions, encoding changes, script additions, or any multi-step implementation
---

# Brainstorming Ideas Into Designs

Help turn ideas into fully formed designs and specs through natural collaborative dialogue.

Start by understanding the current project context, then ask questions one at a time to refine the idea. Once you understand what you're building, present the design and get user approval.

<HARD-GATE>
Do NOT write any code, create any script, or modify any file until you have presented a design and the user has approved it.
</HARD-GATE>

## Checklist

Complete in order:

1. **Explore project context** — check CLAUDE.md, project-rules.md, relevant `src/` modules, recent commits
2. **Ask clarifying questions** — one at a time; understand purpose, constraints, success criteria
3. **Propose 2-3 approaches** — with trade-offs and your recommendation
4. **Present design** — architecture, file layout, data flow, error handling, testing approach; get approval
5. **Write design doc** — save to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` and commit
6. **Spec self-review** — scan for placeholders, contradictions, ambiguity
7. **User reviews written spec** — ask user to review before proceeding
8. **Transition to implementation** — invoke `writing-plans` skill

## Process

**Exploring the idea:**
- Check `src/` module structure and `CLAUDE.md` first
- Ask ONE question at a time — multiple choice preferred
- Focus on: purpose, ROM region affected, encoding considerations, test approach, where output goes

**Example questions for gba_translator:**
- "Which ROM region does this affect? (text 0x1F00000–0x1F80000, Pokédex tables, battle strings, ...)"
- "Does this need to handle French accented characters? Which ones?"
- "Should the output go to `output/` or does it modify the ROM in-place?"
- "Is this a one-time extraction or part of the injection pipeline?"

**Proposing approaches:**
- Always propose 2-3 options with trade-offs
- Lead with your recommendation and explain why
- Consider: complexity, test coverage feasibility, fit with existing `src/core/` classes

**Presenting the design:**
- Cover: which `src/` modules are touched, new classes/functions, data flow, test plan
- Scale to complexity — a small addition needs only a few sentences
- Verify it respects project-rules.md: correct folder, numbered docs, DRY via `src/core/`

## Project Conventions to Apply in Design

- New scripts → `src/extractors/NN_name.py`, `src/analyzers/NN_name.py`, etc. (numbered)
- New docs → `docs/NN_NAME.md` (numbered, UPPER format)
- Common code → `src/core/` (DRY — never duplicate between scripts)
- All outputs → `output/` subdirectory with `YYYY-MM-DD_` prefix
- Tests → `tests/unit/test_<module>.py` or `tests/integration/`
- Commit format: `feat(scope): description`

## After the Design

- Write spec to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
- Run spec self-review (placeholders? contradictions? ambiguity?)
- Ask user to review the written spec
- Then invoke `writing-plans` skill — that is the ONLY next step

## Key Principles

- **One question at a time** — don't overwhelm
- **YAGNI ruthlessly** — remove unnecessary features
- **Explore alternatives** — always 2-3 approaches before settling
- **DRY by design** — shared logic belongs in `src/core/` from day one
