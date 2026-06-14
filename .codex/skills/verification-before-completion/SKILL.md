---
name: verification-before-completion
description: Use before claiming work is complete — run verification commands and cite output before any success claim
when_to_use: Before any "done", commit, PR, or task completion claim
---

# Verification Before Completion

## Overview

Claiming work is complete without verification is dishonesty, not efficiency.

**Core principle:** Evidence before claims, always.

**Project rule:** 100% test pass rate is mandatory. "Looks good" is not evidence.

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

## The Gate Function

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying
```

## Verification Commands (gba_translator)

```bash
# Full test suite — must show 0 failures, 0 errors
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests (some require mGBA — skip if not available)
pytest tests/integration/ -v

# With coverage
pytest --cov=src tests/

# Check no stray files at repo root
ls *.py 2>/dev/null && echo "FAIL: py files at root" || echo "OK"
ls *.md 2>/dev/null | grep -v README.md && echo "FAIL: md files at root" || echo "OK"
```

## Common Failure Patterns

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | `pytest tests/` → 0 failures | "Should pass", previous run |
| Feature works | Test exercising the feature passes | Code reviewed and looks correct |
| Bug fixed | Test reproducing the bug now passes | Code changed, assumed fixed |
| 100% pass rate | `pytest tests/` → 100% of N tests | "All critical tests pass" |
| ROM output correct | Injection + decode round-trip passes | Manual visual inspection |
| No regression | Full `pytest tests/` after change | Subset of tests passes |

## Red Flags — STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before running tests ("Great!", "Done!")
- About to commit without running `pytest tests/`
- "All tests pass" without showing the command output
- Running only `tests/unit/` and claiming full pass

## Project-Specific Rules

1. **100% pass rate**: If even ONE test fails, work is not done. No exceptions.
2. **No skips**: A skipped test is not a passing test.
3. **Integration tests**: If your change touches the pipeline, run `pytest tests/integration/` too.
4. **Root clean**: Before committing, verify no `.py` or `.md` files landed at repo root.

## The Bottom Line

Run the command. Read the output. THEN claim the result.

```
✅ $ pytest tests/
   534 passed, 0 failed, 0 errors in 12.3s
   → "All tests pass."

❌ "Tests should pass now."
❌ "I've verified the fix works."
```
