---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes
when_to_use: Any bug, failing test, encoding error, pointer corruption, or unexpected ROM output
---

# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Project rule:** 100% test pass rate required. Any failure demands root cause investigation, not a skip.

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## The Four Phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Read Error Messages Carefully**
   - Full pytest traceback — don't skim
   - Note the exact offset, byte value, or encoded character
   - For ROM issues: print the raw hex bytes around the failure point

2. **Reproduce Consistently**
   ```bash
   pytest tests/unit/test_<module>.py::test_name -v -s
   ```
   - Can you trigger it reliably?
   - Does it happen every time?
   - Same byte, same offset, same charmap entry?

3. **Check Recent Changes**
   ```bash
   git diff HEAD~1
   git log --oneline -5
   ```

4. **Gather Evidence in Multi-Layer Pipeline**

   The gba_translator pipeline layers: ROM → Pointer → Decoder → Injector → Validator → IPS patch
   
   For each layer, log what enters and exits:
   ```python
   # Print raw bytes before decode
   print(f"raw bytes: {data.hex()}")
   # Print decoded text
   print(f"decoded: {repr(text)}")
   # Print re-encoded bytes
   print(f"re-encoded: {encoded.hex()}")
   ```
   
   Identify exactly WHICH layer corrupts the data.

5. **Trace Data Flow**
   - Where does the bad value originate?
   - What called this with the bad value?
   - Trace backward through call stack to the source
   - Fix at source, not at symptom

### Phase 2: Pattern Analysis

1. **Find Working Examples**
   - Is there a similar string that encodes correctly?
   - Compare the Spanish ROM reference (`spanishrom.gba`) as ground truth
   - Check `src/text/charmap_data.py` for the mapping

2. **Identify Differences**
   - List every difference between working and broken cases
   - Don't assume "that can't matter" (byte order, terminator, control codes all matter)

### Phase 3: Hypothesis and Testing

1. **Form Single Hypothesis** — state clearly: "I think X is the root cause because Y"
2. **Test Minimally** — smallest possible change, one variable at a time
3. **Verify Before Continuing** — run `pytest tests/` after each change

**If 3+ fixes failed:** Question the architecture, not the individual fix.

### Phase 4: Implementation

1. **Create Failing Test First** (see `test-driven-development` skill)
   ```python
   def test_specific_bug_reproduction():
       # Exact reproduction of the failure
       result = encoder.decode(bytes([0xFA, 0x01]))  # control code edge case
       assert result == expected_output
   ```

2. **Implement Single Fix** — address root cause only, no bundled refactoring

3. **Verify Fix**
   ```bash
   pytest tests/ -v  # ALL tests must pass — 100% required
   ```

4. **If Fix Doesn't Work** — STOP, return to Phase 1 with new evidence

## Common gba_translator Bug Categories

| Symptom | Likely Root Cause | Where to Look |
|---------|-------------------|---------------|
| Wrong character displayed | Charmap mismatch | `src/text/charmap_data.py` |
| String truncated | 0xFF terminator missing | `src/text/encoder.py` |
| Garbage after text | Pointer not updated | `src/inject/repointer.py` |
| Crash on injection | Free space overrun | `src/inject/space_manager.py` |
| Control code ignored | FC/FD/F8/F9 multi-byte not handled | `src/text/charmap_data.py` |
| IPS patch wrong | Binary diff error | `src/pipeline/` |

## Red Flags — STOP and Follow Process

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "It's probably a charmap issue" (without checking)
- "Skip this test, it's a ROM edge case"
- "One more fix attempt" (when already tried 2+)

**ALL of these mean: STOP. Return to Phase 1.**

## Quick Reference

| Phase | Key Activities | Success Criteria |
|-------|---------------|------------------|
| **1. Root Cause** | Read errors, reproduce, gather hex evidence | Understand WHAT and WHY |
| **2. Pattern** | Compare working vs broken, check charmap | Identify differences |
| **3. Hypothesis** | Form theory, test minimally, one change | Confirmed or new hypothesis |
| **4. Implementation** | Write failing test, fix root cause, verify | All tests pass (100%) |
