# gba_translator — AI Memory (Claude)

> Pokemon Unbound GBA ROM toolkit: reverse-engineers English + Spanish ROMs and
> produces a French ROM translation (CFRU / BPRE01 game engine).

## Stack

| Layer | Tech |
|---|---|
| Language | Python 3.11+ |
| Tests (unit/integration) | pytest |
| Tests (E2E / browser) | Playwright (TypeScript) + mGBA WebSocket |
| Tests (emulator-web) | Vitest |
| ROM emulation | mGBA (headless + WebSocket) |
| Build automation | GNU Make |
| External deps | pyyaml ≥ 6.0, playwright, vitest |

## Folder Map

```
gba_translator/
├── CLAUDE.md               ← this file (Claude AI memory)
├── AGENTS.md               ← Codex AI memory
├── Makefile                ← canonical entry point for all operations
├── pyproject.toml          ← Python project config + pytest markers
├── combined_fr.txt         ← master EN→FR translation file (2 MB, ~9 k entries)
│
├── src/
│   ├── core/               ← shared library (import from here everywhere)
│   │   ├── rom_reader.py           — ROMReader class (load, read/write bytes/pointers)
│   │   ├── text_codec.py           — encode/decode text using POKEMON_TABLE charmap
│   │   ├── text_converter.py       — higher-level text conversion helpers
│   │   ├── text_reinserter.py      — inserts translated text into ROM, handles relocation
│   │   ├── text_validator.py       — validates reinsertion (ranges, overflows)
│   │   ├── padding_detector.py     — detects free bytes after a text block
│   │   ├── enhanced_padding_detector.py — advanced padding analysis
│   │   ├── dialogue_linewrap.py    — line-wrap logic for dialogue boxes (18 chars/line)
│   │   ├── fallback_translator.py  — token-by-token fallback when full text doesn't fit
│   │   └── fixed_tables.py         — list of ROM regions that must not be relocated
│   │
│   ├── extractors/
│   │   └── pointer_text_extractor.py   — scans ROM pointers → extracts all text blocks
│   │
│   ├── analyzers/
│   │   ├── 11_pointer_text_diff.py     — diffs EN vs ES extracts → offset map
│   │   └── (numbered legacy scripts)
│   │
│   ├── translators/
│   │   ├── 19_build_translated_rom_generic.py  — THE build engine (57 KB, main entry point)
│   │   ├── 28_export_trilingual_csv.py          — exports EN/ES/FR trilingual CSV
│   │   └── (numbered legacy variants)
│   │
│   ├── validators/
│   │   └── text_range_validator.py     — byte-for-byte validation vs reference ROM
│   │
│   ├── commands/
│   │   └── build_rom.py                — CLI wrapper for build_translated_rom_generic
│   │
│   ├── text/
│   │   └── charmap_data.py             — raw CFRU charmap table data
│   │
│   ├── utils/                          — misc helpers
│   └── cooker/
│       ├── emulator.py                 — mGBA process launcher + WebSocket client
│       └── checkpoint.py               — saves/restores mGBA savestates for scenario tests
│
├── scripts/                ← standalone CLI tools (not imported as modules)
│   ├── apply_combined_fr.py            — apply combined_fr.txt to a built FR ROM
│   ├── apply_inline_overrides_fr.py    — inject inline text overrides
│   ├── audit_translation_fr.py         — quality audit of FR translation
│   ├── export_dynamic_trilingual_csv.py — dynamic CSV export
│   ├── patch_font_fr.py                — patch ROM font table for FR glyphs
│   ├── patch_fixed_table_names.py      — patch known fixed-table strings (places, NPCs)
│   ├── patch_time_format_fr.py         — patch date/time code to FR format (DD/MM/YYYY, 24h)
│   ├── repoint_stale_text_pointers.py  — fix pointers that still point to old addresses
│   ├── repair_localized_lz77_blocks.py — restore LZ77-compressed images with FR text
│   ├── repair_stable_lz77_blocks.py    — restore LZ77 blocks that regress after injection
│   ├── run_playwright_tests.py         — orchestrates Playwright runs with mGBA
│   ├── spellcheck_combined_fr.py       — spellcheck combined_fr.txt entries
│   ├── sync_charmap.py                 — sync charmap Python→TypeScript
│   └── verify_roms.py                  — verify ROM checksums against docs/roms_baseline.json
│
├── tests/
│   ├── unit/               ← fast, no ROM needed
│   ├── e2e/                ← Python integration tests (need ROM files)
│   ├── e2e-playwright/     ← Playwright specs (need mGBA + ROM)
│   ├── benchmarks/         ← performance benchmarks (slow)
│   └── stress/             ← stress tests (very slow)
│
├── emulator-web/           ← TypeScript browser harness + Vitest unit tests
│   └── src/                — GBA emulator WebAssembly wrapper
│
├── input/
│   └── roms/               ← source ROMs (READ-ONLY, never modify)
│       ├── englishrom.gba  — English source (BPRE01)
│       └── spanishrom.gba  — Spanish community translation (reference)
│
└── output/
    ├── roms/               — built ROMs: GenedRom-es.gba, GenedRom-fr.gba
    ├── extracted/          — pointer-extracted JSON text corpora
    ├── differences/        — EN↔ES diff + offset map JSON
    ├── translation/        — *_translation_ready.json (inputs to build-fr)
    └── reports/            — validation + quality reports
```

## Canonical Commands

```bash
# Install everything
make install                    # pip install -e ".[dev]" + npm install

# Full ES pipeline (extract → diff → build → validate)
make pipeline

# Build French ROM
make build-fr                   # uses latest output/translation/*_translation_ready.json

# Multi-language (see docs/21_MULTILANGUE.md)
make langs                      # list languages declared in languages/<code>/lang.yaml
make build-it                   # Italian (generic driver scripts/build_language.py)
make build-de                   # German  (generic driver)
make build-all                  # FR (dedicated) + IT + DE
make release-all                # build all three + package output/release/

# Tests — fast (unit only, no ROM/emulator)
make test                       # alias: test-python-fast
python3 -m pytest tests/ -x --ignore=tests/benchmarks --ignore=tests/e2e \
    -m "not slow and not stress and not emulator and not rom"

# Tests — standard (unit + integration, no emulator)
make test-python

# Tests — Vitest (emulator-web TypeScript)
make test-vitest

# Tests — Playwright E2E (needs mGBA + ROM)
make test-playwright

# Validate charmap sync (Python ↔ TypeScript)
make sync-charmap-check

# Spellcheck combined_fr.txt
python3 scripts/spellcheck_combined_fr.py

# Quality audit
python3 scripts/audit_translation_fr.py

# List open tickets
make tickets
```

## FR Build Pipeline (step by step)

`make build-fr` runs these in order:
1. `19_build_translated_rom_generic.py` — copy EN ROM, inject translations from JSON
2. `patch_font_fr.py` — add FR glyphs to font table
3. `patch_fixed_table_names.py` — patch hardcoded location/NPC names
4. `patch_time_format_fr.py` — patch Thumb code for DD/MM/YYYY, 24h clock
5. `apply_inline_overrides_fr.py` — inject inline (non-pointer) text overrides
6. `repair_stable_lz77_blocks.py` — restore LZ77-compressed images
7. `repair_localized_lz77_blocks.py` — restore localized LZ77 blocks
8. `repoint_stale_text_pointers.py` — fix any stale pointers after relocation

## Multi-language architecture (FR / IT / DE …)

Languages are declared in a registry: `languages/<code>/lang.yaml`, loaded by
`src/i18n` (`load_registry()`), with translations in
`languages/<code>/combined_<code>.txt` (French keeps `combined_fr.txt` at root).

- **French = `build: dedicated`.** It is COMPLETE and byte-perfect; it keeps the
  full hand-tuned `make build-fr` recipe above. **Never** reroute FR through the
  generic driver — `make build-fr` must keep producing the exact same ROM hash.
- **Italian / German = `build: generic`**, built by `scripts/build_language.py
  <code>`: `combined_<code>.txt` → trilingual CSV (`apply_combined_fr.py`, which
  is language-agnostic) → `<code>_translation_ready.json` → generic builder →
  per-language patches (`font`, `inline`).
- Shared code, per-language data only. `apply_combined_fr.py`,
  `apply_inline_overrides_fr.py`, `patch_font_fr.py` are reused across languages
  via CLI args (the `_fr` name is historical).
- Charmap caveat: `à è é ì í î ò ó ù ú ç ß` encode; `ä ö ü` do **not** yet — German
  transliterates umlauts (`ae/oe/ue/ss`) until a DE charmap+font extension lands.
- `make release-all` → `scripts/package_release.py` writes ROMs + zips +
  `SHA256SUMS.txt` + `RELEASE_MANIFEST.json` to `output/release/`.

Full guide: `docs/21_MULTILANGUE.md`. Tests: `tests/test_language_registry.py`.

## Règle impérative — fichiers `combined_<langue>.txt` (tous agents, toutes langues)

> Les fichiers `combined_<langue>.txt` sont des sources de traduction manuelles et
> cumulatives. Cette règle s'applique au `combined_fr.txt` historique à la racine
> comme à **tous** les fichiers `languages/*/combined_*.txt`, quelle que soit la langue.

- **Interdiction absolue de régénérer, réécrire entièrement, trier, normaliser ou
  reformater** un fichier `combined`. Ne pas le reconstruire depuis une ROM, un CSV,
  un JSON ou un script, et ne pas lancer de remplacement global (`sed`, regex, script
  de masse) dessus.
- Toute correction doit être une **édition chirurgicale** de l'entrée visée : conserver
  l'ordre, les doublons, l'encodage et les fins de ligne existantes. Quand les doublons
  sont résolus par dernière occurrence, localiser et modifier cette dernière occurrence.
- Avant le commit, contrôler le diff : il ne doit contenir que les offsets explicitement
  concernés, sans suppression, déplacement ni modification indirecte d'autres entrées.
- Une régénération n'est acceptable que si le ticket la demande explicitement et fournit
  une procédure de préservation et de vérification des entrées existantes.

## Domain Glossary

| Term | Meaning |
|---|---|
| **GBA** | Game Boy Advance |
| **BPRE01** | Pokemon FireRed ROM identifier |
| **CFRU** | Custom FR engine base used by Pokemon Unbound |
| **charmap** | Table mapping Unicode chars to ROM byte values |
| **POKEMON_TERMINATOR** | `0xFF` — marks end of a string in ROM |
| **POKEMON_NEWLINE** | `0xFE` — line break within a text block |
| **control code** | Multi-byte sequences: `0xFC`, `0xFD`, `0xF8`, `0xF9`, `0xF7` |
| **pointer** | 32-bit LE address in ROM; physical = `value − 0x08000000` |
| **offset** | Byte position in the ROM file |
| **GBA_ROM_BASE** | `0x08000000` — ROM address space base |
| **combined_fr.txt** | Master translation file: `<offset_hex> <FR_text>` lines |
| **translation_ready.json** | Structured JSON consumed by the build engine |
| **offset map** | EN→ES pointer→offset mapping (JSON) |
| **relocation** | Moving a text block to free space when FR text is longer |
| **repoint** | Updating a pointer to its new target after relocation |
| **fixed table** | ROM region whose address must not change (species/move names, etc.) |
| **LZ77** | Compression used for ROM graphics; patches must preserve it |
| **IPS** | ROM patch format (records: offset + bytes) |
| **trilingual CSV** | EN/ES/FR text export for translators |
| **mGBA** | GBA emulator used for Playwright/cooker tests |
| **savestate** | mGBA snapshot — used as fixtures in Playwright tests |

## Key Technical Facts

### Text Encoding
- Proprietary charmap in `src/core/text_codec.py` (`POKEMON_TABLE` + accented extensions)
- Terminator: `0xFF` | Newline: `0xFE` | Space: `0x00`
- FR glyphs: `é è ê ë à â ç ù û ü î ï ô œ` and uppercase variants — all mapped
- Control codes 2–3 bytes: `FC nn`, `FD nn`, `F8 nn`, `F9 nn`, `F7 nn nn`
- `{COLOR}X` → `FC 01 NN`; `{LV}` → `0x34`

### combined_fr.txt — SOURCE DE VÉRITÉ UNIQUE POUR LES TRADUCTIONS FR

> **Ce fichier est le seul endroit où corriger du texte français visible en jeu.**
> Toute correction faite ailleurs (autre repo, JSON intermédiaire, CSV) sera
> écrasée au prochain `make build-fr`.

Format de chaque ligne : `<offset_hex> <texte_FR>` (offset en hexa, espace, texte)

**Règle des doublons (CRITIQUE)**
- ~957 offsets sont présents en double dans le fichier
- `apply_combined_fr.py` lit ligne par ligne avec `mapping[offset] = text` → **la dernière entrée gagne**
- Le bloc en hexa **minuscule** vers la fin du fichier est la version vivante
- Toujours éditer/ajouter dans ce bloc minuscule, jamais dans les entrées du haut

**Workflow d'une correction** (détails : [`docs/20_TRANSLATION_PRESERVATION.md`](docs/20_TRANSLATION_PRESERVATION.md))
1. `git status` propre, puis trouver la **dernière** occurrence de l'offset dans `combined_fr.txt` (grep case-insensitive)
2. Éditer cette ligne (insertion chirurgicale — ne jamais réécrire le fichier entier)
3. `python3 scripts/check_translation_integrity.py` → 13 [OK], exit 0 (garde anti-régression des labels carte)
4. Relancer la chaîne complète : `apply_combined_fr.py --extend` → CSV → JSON → `make build-fr`
5. Vérifier les octets décodés dans la ROM (pas le fichier — des entrées peuvent être ignorées silencieusement)

**Pièges**
- Une entrée avec traduction VIDE ou encore anglaise n'est PAS traduite en ROM
- Une traduction trop longue sans pointeur disponible est silencieusement ignorée
- Ne jamais sauter `apply_combined_fr.py --extend` : les offsets absents du CSV n'atteignent jamais la ROM

### Trilingual CSV (CRLF hazard)
- The CSV file uses CRLF line endings **and** LF inside field values
- Use surgical byte-level insertion; never re-write the whole file

### Pointers
- All text pointers: 32-bit little-endian at `pointer_value − 0x08000000` = file offset
- Valid pointer range: `0x08000000`–`0x0BFFFFFF`

### mGBA Probe Quirks
- `Aaaaaaa`/`Fffffff` in probe output = naming-screen button mash, not real text
- Sudden disconnects on bridge routes = flakiness, not a crash
- **NEVER save in-game** during probe sessions — overwrites `.sav` fixtures → Playwright goldens break
- Use short sessions + savestates

### Date/Time Patches
- `patch_time_format_fr.py` patches Thumb assembly code **post-build**
- Implements DD/MM/YYYY, 24h clock, Dim..Sam, "Jamais" strings

### Gendered buffers
- Son/daughter text: delivered via opcode 85 (son=fils, daughter=fille)
- Avoid "mon {fille}" — use "mon enfant" instead; use il/elle for pronouns

## Non-Obvious Gotchas

1. **combined_fr.txt est la SEULE source de vérité FR** — toute correction de texte visible en jeu doit aller ici, pas dans un autre repo ou fichier intermédiaire. Last entry wins : toujours ajouter/corriger dans le bloc hexa minuscule en bas du fichier.
2. **charmap sync** — Python `text_codec.py` and TypeScript must stay in sync; run `make sync-charmap-check` after any charmap edit.
3. **test markers matter** — `emulator`, `rom`, `slow`, `stress` gates skip in CI. Fast suite: `-m "not slow and not stress and not emulator and not rom"`.
4. **fixed tables** — `src/core/fixed_tables.py` lists regions whose addresses must never change. Passing `--allow-relocate` without this guard corrupts species/move name lookups.
5. **LZ77 regression** — after build-fr, run `repair_stable_lz77_blocks.py`; skipping it causes graphical corruption.
6. **Stale pointers** — text relocation leaves old pointers pointing at garbage; `repoint_stale_text_pointers.py` is mandatory at end of build-fr.
7. **intro font** — glyphs `ê`, `ç`, `ù` are absent from the fullscreen intro font; avoid them in intro text.
8. **mGBA never save** — saving in-game during tests corrupts the `.sav` fixture files.
9. **positional placeholders** — the build engine uses positional token replacement; never swap `{0}` and `{1}` in FR strings.
10. **FA/FB opcodes** — these are outside the token file; do not add them to combined_fr.txt.
11. **Labels carte du monde = inline non-CSV** — les 13 offsets 0xB5xxxx/0x72xxxx (Trou Glacé, Volcan Cendreux, Île de la Lune, etc.) ne sont PAS dans le CSV trilingue. Ils survivent UNIQUEMENT dans combined_fr.txt (bloc bas minuscule). Une réécriture massive — ou une working copy périmée — les ramène silencieusement à l'anglais (c7c1ede a régressé 97 entrées). Un `grep -c` ne suffit PAS : c7c1ede a réécrit les **valeurs**, pas supprimé les lignes. Vérifier après tout edit la valeur résolue : `python3 scripts/check_translation_integrity.py` → 13 [OK], exit 0. Voir [`docs/20_TRANSLATION_PRESERVATION.md`](docs/20_TRANSLATION_PRESERVATION.md).
12. **make test-rom obligatoire** — après tout `make build-fr`, lancer `make test-rom`. Si un test échoue, la ROM est invalide et ne doit pas être committée. Voir `.claude/rules/patterns/forbidden.md#traductions`.
13. **Un fix jamais scopé à une seule langue** — `src/core/`, `scripts/build_language.py`
    et les scripts de patch réutilisés (sans suffixe `_<code>`) servent FR/IT/DE/Indie à
    la fois. Valider un fix qui les touche avec `pytest tests/unit/fr/` seul ne prouve
    rien pour IT/DE ; lancer la suite complète (`make test-python`, qui couvre déjà
    `tests/unit/{fr,it,de,en}` + `tests/e2e/{fr,it,de,es}`) et, si la génération de ROM
    est touchée, rebuild IT/DE (`make build-it && make build-de`). Un bug de table figée /
    contamination du ROM de base découvert côté FR touche souvent aussi IT/DE — vérifier
    avant de clore. Voir `.claude/rules/patterns/multilang-regression.md`.
14. **Snapshot périmé = traductions détruites (Pattern C)** — sur ce dépôt, `HEAD` avance en continu (agents concurrents) et peut même avancer **sous** le checkout partagé sans mise à jour des fichiers. Un commit préparé depuis une copie lue 15 min plus tôt reverte silencieusement les fixes intermédiaires (`9ad0fee` a détruit 5 offsets pour 1 annoncé ; `dc84690f` a re-cassé le template Méga-Cuff ET supprimé son test). Règle absolue : **relire `combined_*.txt` au moment d'éditer**, committer immédiatement (chemins précis, avant tout build), puis **relire le diff du commit** — le moindre offset étranger au périmètre annoncé = `git reset --soft HEAD~1` et refaire sur `HEAD` frais. Toute traduction déjà perdue une fois s'ajoute à `CRITICAL_LABELS` (`scripts/check_translation_integrity.py`). Détails : [`docs/20_TRANSLATION_PRESERVATION.md`](docs/20_TRANSLATION_PRESERVATION.md) §7.

## AI Configuration & capabilities

Coding conventions and agent wiring live alongside this memory file:

- **Rules** : [`.claude/project-rules.md`](.claude/project-rules.md) (architecture, source de
  vérité) + [`.claude/rules/patterns/`](.claude/rules/patterns/00_index.md) (style par domaine :
  python, archi, scripts, encodage, tests, outillage, nommage, interdits, git) +
  [`.claude/rules/multitasking.md`](.claude/rules/multitasking.md) (worktrees, ports, concurrence).
- **Sous-agents** : `rom-analyzer`, `translation-verifier`, `test-runner`
  ([`.claude/agents/`](.claude/agents)).
- **Slash commands** : `/build-fr`, `/run-tests`, `/sync-charmap`, `/validate-rom`
  ([`.claude/commands/`](.claude/commands)).
- **Skills** : [`.claude/skills/`](.claude/skills/README.md) (ordre de découverte :
  plugins → projet → rédaction fraîche).
- **Hooks** : PreToolUse bloque le contournement de hooks git / merge non-rebase /
  écriture dans `input/roms/` ; PostToolUse lance `ruff`
  ([`.claude/settings.json`](.claude/settings.json), scripts dans `.claude/hooks/`).
- **MCP** : filesystem, image-tools, git ([`.mcp.json`](.mcp.json)).

> Le projet est francophone : commits `type(scope): description` en français, **jamais**
> de trailer `Co-Authored-By`, **jamais** contourner le hook pre-commit, rebase only.
