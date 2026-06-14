---
name: writing-plans
description: Convert a spec or requirement into a numbered, executable implementation plan
when_to_use: After brainstorming approval, before touching any code
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context of the codebase. Document everything they need: which files to create/modify, exact commands, test code, expected output. Bite-sized TDD tasks. DRY. YAGNI. Frequent commits.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Save plans to:** `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`

## Scope Check

If the spec covers multiple independent subsystems (extraction + injection + validation + IPS patch), suggest breaking into separate plans — one per subsystem. Each plan should produce testable, working software on its own.

## File Structure First

Before defining tasks, map which files will be created or modified:

```
Create: src/core/new_module.py
Modify: src/text/encoder.py (add method to existing class)
Create: tests/unit/test_new_module.py
Modify: src/pipeline/orchestrator.py (wire new module)
```

Follow project-rules.md:
- New scripts → `src/extractors/NN_name.py`, `src/analyzers/NN_name.py`, etc.
- Common logic → `src/core/` (DRY)
- Tests → `tests/unit/test_<module>.py`
- Outputs → `output/` with `YYYY-MM-DD_` prefix

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" — step
- "Run it to verify it fails" — step
- "Implement the minimal code" — step
- "Run tests to verify they pass" — step
- "Commit" — step

## Plan Document Header

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** Use `test-driven-development` and `verification-before-completion` skills on each task.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** Python 3.11+, pytest, pyyaml

---
```

## Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `src/core/new_class.py`
- Create: `tests/unit/test_new_class.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_new_class.py
def test_specific_behavior():
    obj = NewClass()
    result = obj.do_thing(input_data)
    assert result == expected_output
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_new_class.py::test_specific_behavior -v
```

Expected: FAIL with "NewClass not defined" or "AttributeError"

- [ ] **Step 3: Write minimal implementation**

```python
# src/core/new_class.py
class NewClass:
    def do_thing(self, data):
        return expected_output
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/ -v
```

Expected: All tests PASS (100% required — project-rules.md)

- [ ] **Step 5: Commit**

```bash
git add tests/unit/test_new_class.py src/core/new_class.py
git commit -m "feat(core): add NewClass for specific behavior"
```
````

## No Placeholders

Never write:
- "TBD", "TODO", "implement later"
- "Add appropriate error handling" (without showing code)
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the full code — tasks are read independently)
- References to functions not defined in any task

## Project-Specific Reminders

- 100% test pass rate required after every task (`pytest tests/`)
- Docstrings + type hints on all public functions
- Common code → `src/core/` (never duplicate)
- Backups before ROM writes (`.gba.bak`)
- Outputs → `output/YYYY-MM-DD_name.ext`
- Commit format: `feat(scope): description`

## Self-Review

After writing the complete plan:

1. **Spec coverage:** Can you point to a task for every requirement? List gaps.
2. **Placeholder scan:** Search for TBD/TODO/vague steps. Fix them.
3. **Type consistency:** Do method names match across tasks?

Fix issues inline. Then offer execution choice to the user.
