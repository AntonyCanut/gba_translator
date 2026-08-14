# Pokémon Unbound — Multi-language ROM Translation Toolkit

[![](https://dcbadge.limes.pink/api/server/https://discord.gg/ctFaR77WrR)](https://discord.gg/ctFaR77WrR)

Open-source toolkit used to translate **Pokémon Unbound** from English into multiple languages.

The project started from a Spanish reproduction / reverse-engineering pipeline and now provides a multi-language build system for French, Italian, German and experimental language targets.

French is the reference translation: it is complete, byte-perfect, and built through a dedicated recipe to avoid regressions. Other languages are driven by the generic multi-language pipeline.

## Community

The Discord server is the main place to discuss the project, ask questions, report translation issues, share screenshots, and coordinate contributions.

Join the community here:

[Discord Community](https://discord.gg/ctFaR77WrR)

You can use Discord for:

- Reporting translation mistakes
- Sharing screenshots of text or layout issues
- Asking for help with the toolkit
- Discussing translation decisions
- Suggesting improvements
- Coordinating contributions

## Reporting bugs and issues

You can report bugs in two ways:

- Create a GitHub issue in this repository
- Post directly in the Discord community

### Translation issues

For translation mistakes, typos, wrong wording, or text layout problems, a simple screenshot is usually enough.

Please include the language concerned and, if possible, the in-game location or context where the text appears.

### Blocking bugs

For blocking issues such as freezes, soft locks, broken events, progression blockers, corrupted UI, or unexpected behavior, please provide:

- A clear description of the problem
- The steps required to reproduce it
- A screenshot or short video if relevant
- The `.sav` file from the affected location

A save file is extremely useful because it makes the issue reproducible and reduces the time needed to fix it.

## Contributing

This repository is open source. Contributions are welcome through Pull Requests.

You can contribute by:

- Fixing translation mistakes
- Improving existing translations
- Adding missing translated strings
- Testing ROM builds
- Reporting regressions
- Improving scripts, build tooling, or documentation
- Adding support for new languages

Every Pull Request is analyzed by an AI assistant to check its viability, detect potential implementation issues, and speed up the review process. Final decisions remain under human supervision.

## AI-assisted development with Singularity

Most of this project is developed with **Singularity**, an AI-assisted development environment created to improve productivity on complex software projects.

Singularity helps with:

- AI-assisted implementation workflows
- Code review preparation
- Repository context management
- Task decomposition
- Faster iteration on translation tooling
- Safer refactoring of large codebases

Learn more here:

[Singularity](https://singularity.meteorfactory.dev/)

Contributors can work with any workflow they prefer. Singularity is not required to contribute, but it is the main development environment used on this project.

## Current language status

| Language | Status | Build mode | Local build output |
| --- | --- | --- | --- |
| French | Complete | Dedicated | `GenedRom-fr.gba` |
| Italian | In progress | Generic | `GenedRom-it.gba` |
| German | In progress | Generic | `GenedRom-de.gba` |
| Indie | Experimental | Generic | `GenedRom-indie.gba` |

French must stay isolated from the generic driver. The dedicated French build exists to keep the validated ROM stable and byte-perfect.

## Released patches

GitHub releases and the tracked `patches/` directory contain BPS patches
only. Download `pokemon_unbound_<language>.bps`, verify the SHA-256 of the
required source ROM in `RELEASE_MANIFEST.json`, then apply the patch with a
BPS-compatible patcher. Keep the source ROM unchanged and save the generated
ROM under a new name.

Every build remains available under `v2.1.<build>`. The `latest` release is a
rolling alias replaced by the newest build. Both releases also include the
global `RELEASE_MANIFEST.json` and `SHA256SUMS.txt`; publication starts only
after the FR, IT, DE and Indie artifacts have all been verified. GitHub
Actions validates and publishes these tracked files without downloading,
building or uploading any ROM.

## Translation methods

There are several ways to help translate the project, depending on how technical you want to be.

### 1. Report translation issues on Discord

This is the easiest contribution method.

If you find a wrong translation, typo, missing accent, broken line break, or awkward wording, send a screenshot on Discord. This is usually enough for small text fixes.

### 2. Edit an existing language file

Translations are stored in language-specific files:

```text
languages/fr/combined_fr.txt
languages/it/combined_it.txt
languages/de/combined_de.txt
languages/indie/combined_indie.txt
```

Each entry follows this format:

```text
<offset_hex>: <translated text>
```

Special control sequences are used by the game text engine:

| Sequence | Meaning |
| --- | --- |
| `\n` | Line break |
| `\l` | Scroll marker |
| `\p` | Clear / next text box marker |

When editing translations, keep the offset unchanged and only modify the translated text after `: `.

### 3. Add or improve a language

Each language is declared in a descriptor:

```text
languages/<code>/lang.yaml
```

The descriptor defines the language code, native name, build mode, translation file, output ROM name, version label, font glyphs, status abbreviations, and post-build patches.

To add a new generic language:

```bash
mkdir languages/<code>
cp languages/it/lang.yaml languages/<code>/lang.yaml
touch languages/<code>/combined_<code>.txt
make build-lang LANG_CODE=<code>
python3 -m pytest tests/test_language_registry.py
```

### 4. Use AI-assisted translation carefully

AI can help draft or review translations, but generated text should be checked manually before being merged.

The game has strict constraints around line length, control codes, context, gendered text, UI labels, and ROM-specific encoding. A translation that reads well outside the game can still break layout or gameplay if these constraints are ignored.

## Requirements

- Python 3.11+
- Make
- Node.js and npm for emulator and Playwright-based tests
- A legally obtained Pokémon Unbound-compatible English ROM, only for local
  ROM/E2E tests or maintainer builds
- The private patched-FR and Spanish reference ROMs only when regenerating the
  translation patches as a maintainer

Install project dependencies:

```bash
make install
```

Install Playwright browsers when running E2E tests:

```bash
make install-playwright
```

## Patch-first setup for local work

ROM files are not provided by this repository.

For ordinary work and E2E validation, place only the compatible English
Pokémon Unbound ROM here:

```text
input/roms/englishrom.gba
```

The expected SHA-256 is
`7aa25bbf568f7cfcf6ee1cf2e9e6ff637350b3d0705c2375cabb6baa7d9739f7`.
The file remains local and ignored by Git. It is never sent to GitHub Actions.

Validate the tracked bundle without any ROM, then materialize the four local
test ROMs:

```bash
make verify-patches
make materialize-test-roms
```

The BPS source CRC, source SHA-256, target CRC and target SHA-256 are all
checked. Generated files are written under `output/roms/`; an existing target
is preserved as `.gba.bak` before replacement.

Playwright commands perform this materialization automatically:

```bash
npm run test:e2e:boot
npm run test:e2e:translation
npm run test:e2e:german
npm run test:e2e:hp-bar
```

No network access is used by the materializer.

### Maintainer-only patch regeneration

Regenerating a release bundle still exercises the historical source builder.
For that operation only, also place:

```text
input/roms/patchedfrenchrom.gba
input/roms/spanishrom.gba
```

`englishrom.gba` must be a clean vanilla Unbound ROM — it is the base for
`build-es`, the generic multi-language driver (`build-it`/`build-de`/
`build-indie`/`build-lang`) and all shared extraction/diff tooling.
`patchedfrenchrom.gba` is the ROM lineage with official French already baked
into it; it is the base for `build-fr` only (see docs/ROM_SOURCES.md). The
Spanish ROM is required for the original reproduction pipeline and for
validation / pointer-proof workflows.

Choose a new positive build number, rebuild and test locally, then promote the
verified BPS into the tracked bundle:

```bash
make update-patches BUILD_NUMBER=43
make test-private-build
make materialize-test-roms
make test-rom
make test-playwright
```

Review and commit `patches/` together with the source changes. CI only
revalidates and publishes that exact bundle as `v2.1.43` and `latest`.

## Build commands

List registered languages:

```bash
make langs
```

Build the French ROM:

```bash
make extract
make prepare-fr
make build-fr
```

Build generic languages:

```bash
make build-it
make build-de
make build-indie
```

Build any registered generic language:

```bash
make build-lang LANG_CODE=it
```

Build every language:

```bash
make build-all
```

Create redistributable BPS patches:

```bash
make release-all
```

This maintainer command writes a candidate bundle into:

```text
output/release/
```

Promote it only after local validation:

```bash
python3 scripts/promote_patch_bundle.py
```

No ROM is published. Each BPS must be applied to the exact local source listed
in `RELEASE_MANIFEST.json`; the patch verifies the source CRC before
producing the translated ROM. The GitHub workflow keeps every
`v2.1.<build>` release and replaces the rolling `latest` release without
requiring any ROM secret.

## Spanish reproduction pipeline

The historical foundation of the project is the Spanish reproduction pipeline.

Run it with:

```bash
make pipeline
```

This workflow:

1. Verifies ROM baseline metadata
2. Extracts pointer-based texts from English and Spanish ROMs
3. Diffs text ranges and builds an offset map
4. Rebuilds a Spanish ROM from the reference data
5. Validates text ranges byte-for-byte

## Validation and tests

Run the fast Python test suite:

```bash
make test
```

Run the standard Python test suite:

```bash
make test-python
```

Run ROM-specific tests:

```bash
make test-rom
```

This first reconstructs FR, IT, DE and Indie from `patches/` and the local
`input/roms/englishrom.gba`; it does not rerun the private source builder.

Run Vitest checks for the emulator web tooling:

```bash
make test-vitest
```

Run Playwright E2E tests:

```bash
make test-playwright
```

The command applies the tracked FR patch locally before starting Playwright.
Language-specific npm commands do the same for DE and for the multi-ROM
HP-bar scenario.

Run the full available test suite:

```bash
make test-all
```

## Outputs

Common generated outputs:

```text
output/extracted/extracted_texts/
output/differences/
output/translation/
output/roms/
output/reports/
output/release/
```

The generated ROM files are temporary local build outputs under:

```text
output/roms/
```

Release-ready BPS files are written under:

```text
output/release/
```

## Documentation

Useful documentation entry points:

- [Multi-language builds](docs/21_MULTILANGUE.md)
- [Pipeline details](docs/00_README.md)
- [ROM sources and baseline](docs/ROM_SOURCES.md)
- [Generic ROM builder notes](docs/ROM_BUILDING.md)

## Legacy scripts

Older translation pipeline scripts are kept for reference under:

```text
scripts/legacy/
```

The supported entry points are the Makefile targets and the current multi-language pipeline.

## Legal note

This repository does not provide ROM files.

Pokémon is owned by Nintendo, Game Freak, and The Pokémon Company. Pokémon Unbound is a fan-made ROM hack. This project is an unofficial translation toolkit and is not affiliated with or endorsed by the original rights holders.
