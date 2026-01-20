# ROM Sources and Baseline

This project uses two ROMs as the only source of truth:
- input/roms/englishrom.gba
- input/roms/spanishrom.gba

Baseline metadata (size + sha256):
- docs/roms_baseline.json

Baseline metrics (text counts and diffs):
- docs/baseline_report.json

Verify inputs before any build:
- python3 scripts/verify_roms.py --baseline docs/roms_baseline.json

If the ROMs ever change, regenerate the baseline file and update docs.
