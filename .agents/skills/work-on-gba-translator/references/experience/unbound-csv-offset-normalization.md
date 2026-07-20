---
name: unbound-csv-offset-normalization
description: CSV offset formatting inconsistency causes duplicate JSON entries and injection failure
metadata:
  node_type: memory
  type: feedback
  originSessionId: ca43248b-6871-40ff-a637-08ee2094ced2
---

## The Issue

When building trilingual CSV files for the pipeline, offset hex values can be formatted inconsistently:
- `0x0027795D` (8-character format with leading zeros)
- `0x27795D` (7-character format without leading zeros)

These represent the **same offset** (2586973 decimal) but the CSV-to-JSON converter treats them as **separate keys** when the CSV uses both formats in the same file.

## Why This Breaks Translation Injection

1. CSV has two rows for same offset with different hex formats
2. Converter creates **two entries** in JSON for the same offset
3. Build process encounters duplicate entries: doesn't know which one to use
4. Injection pipeline fails or skips one of them
5. Result: Translation doesn't appear in ROM despite being in JSON

## The Fix

**Step 1:** Normalize all offsets in CSV to 8-character format
```python
offset_val = int(offset_str, 16)  # Parse hex
row['offset'] = f"0x{offset_val:08X}"  # Normalize to 0xXXXXXXXX
```

**Step 2:** Remove exact duplicates after normalization
Keep first occurrence, drop later ones. The memory rule "last entry wins" applies to SOURCE files (combined_fr.txt), not to pipeline outputs.

**Step 3:** Regenerate JSON and rebuild ROM
```bash
python3 src/translators/09_csv_to_json_v2.py <fixed_csv>
make build-fr
```

## Prevention

Always ensure CSV exports use consistent offset formatting. Check for `0x0` vs `0x` prefixes before running the converter.

## Why:
Stealth Rock effect (0x27795D) failed to inject despite correct French text in the pipeline because the CSV had both `0x0027795D` and `0x27795D`, creating a duplicate-entry collision.

## How to apply:
Before running `09_csv_to_json_v2.py`, verify the CSV has consistent 8-character hex format for all offsets. Use a normalization pass to catch and fix this silently.
