---
name: commands
description: Canonical CLI commands for gba_translator — install, test, build, lint, audit
metadata:
  type: reference
---

## Install

```bash
make install             # pip install -e ".[dev]" + npm install + emulator-web npm install
make install-playwright  # install Playwright browser (chromium)
```

## Tests

```bash
make test                # fast unit tests (no ROM/emulator)
make test-python         # standard Python tests (no emulator/stress)
make test-vitest         # Vitest for emulator-web TypeScript
make test-playwright     # Playwright E2E (needs mGBA + ROMs)
make test-all            # all three in sequence

# Explicit pytest fast profile:
python3 -m pytest tests/ -x \
    --ignore=tests/benchmarks --ignore=tests/e2e \
    -m "not slow and not stress and not emulator and not rom"
```

## Pipeline (EN→ES)

```bash
make pipeline       # verify-roms → extract → diff → build-es → validate-es
make verify-roms    # ROM checksum check
make extract        # pointer text extraction (EN + ES)
make diff           # EN↔ES pointer diff + offset map
make build-es       # build Spanish ROM copy
make validate-es    # byte-for-byte validation
```

## French ROM

```bash
make build-fr                           # full FR build (uses latest translation_ready.json)
make trilingual-csv                     # export EN/ES/FR trilingual CSV
python3 scripts/audit_translation_fr.py # quality audit (GOOD/ACCEPTABLE/BAD)
python3 scripts/spellcheck_combined_fr.py  # spellcheck combined_fr.txt
```

## Charmap sync

```bash
make sync-charmap        # sync Python charmap → TypeScript
make sync-charmap-check  # dry-run (verify only, no write)
```

## Misc

```bash
make tickets             # list open tickets (scripts/list_tickets.py)
make lint                # pytest --collect-only (verify test collection)
make clean               # remove pipeline output files
make help                # print all Makefile targets
```

**Links:** [[project-overview]] [[fr-pipeline]]
