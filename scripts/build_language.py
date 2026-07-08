#!/usr/bin/env python3
"""Generic, language-agnostic ROM build driver.

Builds a translated Pokémon Unbound ROM for any ``build: generic`` language
declared in the ``languages/`` registry (currently Italian and German).

    python3 scripts/build_language.py it
    python3 scripts/build_language.py de --build-number 3

French is intentionally **not** built here: it uses the dedicated, byte-perfect
``make build-fr`` recipe. Asking this driver to build French prints how to do it
and exits, so the proven FR pipeline can never be byte-drifted by accident.

Pipeline for a generic language:
    1. ensure EN/ES pointer extractions exist
    2. combined_<code>.txt → trilingual CSV → translation-ready JSON
    3. generic ROM builder (relocate + fallback)
    4. language-agnostic post-build patches declared in the descriptor
       (`font`, `inline`, …)
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.i18n import RegistryError, load_registry  # noqa: E402

PYTHON = sys.executable or "python3"

ENGLISH_ROM = REPO_ROOT / "input/roms/englishrom.gba"
SPANISH_ROM = REPO_ROOT / "input/roms/spanishrom.gba"
EXTRACT_DIR = REPO_ROOT / "output/extracted/extracted_texts"
ENGLISH_EXTRACT = EXTRACT_DIR / "englishrom_texts.json"
SPANISH_EXTRACT = EXTRACT_DIR / "spanishrom_texts.json"
TRANSLATION_DIR = REPO_ROOT / "output/translation"

EXTRACT_SCRIPT = REPO_ROOT / "src/extractors/pointer_text_extractor.py"
BUILD_SCRIPT = REPO_ROOT / "src/translators/19_build_translated_rom_generic.py"
CSV_TO_JSON_SCRIPT = REPO_ROOT / "src/translators/09_csv_to_json_v2.py"
APPLY_COMBINED_SCRIPT = REPO_ROOT / "scripts/apply_combined_fr.py"
_PATCH_FONT_FR = REPO_ROOT / "languages/fr/patches/font.py"
INLINE_SCRIPT = REPO_ROOT / "scripts/apply_inline_overrides_fr.py"

# Anti-freeze / anti-corruption patches (language-agnostic mechanics).
REPAIR_LZ77_SCRIPT = REPO_ROOT / "scripts/repair_stable_lz77_blocks.py"
REPAIR_LOCALIZED_LZ77_SCRIPT = REPO_ROOT / "scripts/repair_localized_lz77_blocks.py"
REPOINT_STALE_SCRIPT = REPO_ROOT / "scripts/repoint_stale_text_pointers.py"
PATCH_RITUAL_SCRIPT = REPO_ROOT / "languages/fr/patches/legendary_ritual.py"
PATCH_VERSION_SCRIPT = REPO_ROOT / "languages/fr/patches/version.py"
PATCH_INTRO_QUESTIONS_IT_SCRIPT = REPO_ROOT / "languages/it/patches/intro_questions.py"
PATCH_TRAINER_CLASS_NAMES_IT_SCRIPT = REPO_ROOT / "scripts/patch_trainer_class_names_it.py"
PATCH_LONG_DIALOGUES_IT_SCRIPT = REPO_ROOT / "scripts/patch_long_dialogues_it.py"
CHECK_TRANSLATION_INTEGRITY_SCRIPT = REPO_ROOT / "scripts/check_translation_integrity.py"

# Text patches that can be parameterised with the language's combined file.
PATCH_STATUS_ABBREVS_SCRIPT = REPO_ROOT / "languages/fr/patches/status_abbrevs.py"
PATCH_TM_ITEM_DESC_SCRIPT = REPO_ROOT / "languages/fr/patches/tm_item_descriptions.py"
PATCH_MOVE_DESC_SCRIPT = REPO_ROOT / "languages/fr/patches/move_descriptions.py"

# Graphic (LZ77 tile) patches whose glyphs differ per language, so each ships a
# dedicated per-language script (patch_status_badges_<code>.py). Unlike the text
# status_abbrevs table, the in-battle status badges are drawn as tiles and must
# be redrawn with the target language's letter shapes.
PATCH_STATUS_BADGES_FR_SCRIPT = REPO_ROOT / "languages/fr/patches/status_badges.py"

# Battle-text / control-code-timing / positional-gender-buffer patches. Each
# ships a dedicated per-language script (patch_<name>_<code>.py) because the
# phrasing and byte-budget constraints are language-structure specific; the FR
# script is the fallback for languages that have not ported it yet.
PATCH_BATTLE_PREFIX_FR_SCRIPT = REPO_ROOT / "languages/fr/patches/battle_prefix.py"
PATCH_BATTLE_RECALL_STRINGS_FR_SCRIPT = REPO_ROOT / "languages/fr/patches/battle_recall_strings.py"
PATCH_BATTLE_STRING_TEMPLATES_FR_SCRIPT = REPO_ROOT / "languages/fr/patches/battle_string_templates.py"
PATCH_GENDERED_BUFFERS_FR_SCRIPT = REPO_ROOT / "languages/fr/patches/gendered_buffers.py"
PATCH_GIVECS_GIFT_ITEM_FR_SCRIPT = REPO_ROOT / "languages/fr/patches/givecs_gift_item.py"

# German-only post-build patches: fixed-width name/description tables whose
# translated content is baked into the script (official German localisation),
# not read from combined_de.txt — so, unlike the steps above, these have no
# generic "run the FR script with --combined" delegation and are wired
# directly to their languages/de/patches/<name>.py implementation.
PATCH_ITEM_NAMES_DE_SCRIPT = REPO_ROOT / "languages/de/patches/item_names.py"
PATCH_NATURE_NAMES_DE_SCRIPT = REPO_ROOT / "languages/de/patches/nature_names.py"
PATCH_CFRU_TYPE_NAMES_DE_SCRIPT = REPO_ROOT / "languages/de/patches/cfru_type_names.py"
PATCH_SUMMARY_LABELS_DE_SCRIPT = REPO_ROOT / "languages/de/patches/summary_labels.py"
PATCH_OPTIONS_FOOTER_DE_SCRIPT = REPO_ROOT / "languages/de/patches/options_footer.py"
PATCH_SHOP_DE_SCRIPT = REPO_ROOT / "languages/de/patches/shop.py"
PATCH_PC_MESSAGES_DE_SCRIPT = REPO_ROOT / "languages/de/patches/pc_messages.py"

# Post-build verification (language-agnostic): audit the finished ROM for
# inter-cell text collisions — a translated string not terminated before the
# next live cell fuses with / overwrites its neighbour and can freeze the game.
AUDIT_COLLISIONS_SCRIPT = REPO_ROOT / "scripts/audit_translation_collisions.py"

# Diff + trilingual-CSV generation (needed when output/translation/ is empty).
DIFF_SCRIPT = REPO_ROOT / "src/analyzers/11_pointer_text_diff.py"
TRILINGUAL_SCRIPT = REPO_ROOT / "src/translators/28_export_trilingual_csv.py"
DIFF_DIR = REPO_ROOT / "output/differences"
DIFF_REPORT = DIFF_DIR / "pointer_text_differences.json"
PAIRS_REPORT = DIFF_DIR / "pointer_translation_pairs.json"
OFFSET_MAP = DIFF_DIR / "pointer_offset_map.json"
# Dedicated, language-neutral (EN/ES only, no --french) base CSV shared by
# every generic-language build. Deliberately NOT named like the per-language
# outputs (`{code}_trilingual_translation.csv`) so it can never be confused
# with — or accidentally regenerated from — another language's leftover
# translations (see build B-160: DE inherited stale French Pokédex text
# because the old "pick whatever *_trilingual_translation.csv is newest"
# logic could return FR's or IT's own output CSV).
GENERIC_BASE_CSV = TRANSLATION_DIR / "generic_base_trilingual.csv"


def run(cmd: list, *, cwd: Path = REPO_ROOT) -> None:
    printable = " ".join(str(part) for part in cmd)
    print(f"\n$ {printable}")
    subprocess.run([str(part) for part in cmd], cwd=str(cwd), check=True)


def check_translation_integrity(code: str) -> None:
    """Block generic builds when protected combined entries drift."""
    run([PYTHON, CHECK_TRANSLATION_INTEGRITY_SCRIPT, "--lang", code])


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem.lstrip("0123456789_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_extractions() -> None:
    if not ENGLISH_ROM.exists():
        raise SystemExit(f"English ROM not found: {ENGLISH_ROM}")
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    if not ENGLISH_EXTRACT.exists():
        run([PYTHON, EXTRACT_SCRIPT, ENGLISH_ROM, "--output", ENGLISH_EXTRACT, "--scan-all-pointers"])
    if SPANISH_ROM.exists() and not SPANISH_EXTRACT.exists():
        run([PYTHON, EXTRACT_SCRIPT, SPANISH_ROM, "--output", SPANISH_EXTRACT, "--scan-all-pointers"])


def _generic_base_csv() -> Path:
    """Return the language-neutral EN/ES trilingual CSV, generating it if necessary.

    Every generic-language build (DE, IT, …) starts from this single,
    dedicated file so a translation with no entry in its own
    ``combined_<code>.txt`` keeps the English source text instead of
    silently inheriting another language's leftover translation.
    """
    if GENERIC_BASE_CSV.exists():
        return GENERIC_BASE_CSV

    # No trilingual CSV found — generate it automatically.
    if not DIFF_REPORT.exists():
        if not ENGLISH_EXTRACT.exists() or not SPANISH_EXTRACT.exists():
            raise SystemExit(
                "Cannot generate trilingual CSV: extraction files are missing. "
                "Re-run `make build-it` from scratch (source ROMs are required)."
            )
        DIFF_DIR.mkdir(parents=True, exist_ok=True)
        run([
            PYTHON, DIFF_SCRIPT,
            "--english", ENGLISH_EXTRACT,
            "--spanish", SPANISH_EXTRACT,
            "--diff-out", DIFF_REPORT,
            "--pairs-out", PAIRS_REPORT,
            "--map-out", OFFSET_MAP,
        ])

    TRANSLATION_DIR.mkdir(parents=True, exist_ok=True)
    # Pass the EN extraction explicitly to avoid depending on *_diff_with_padding.json.
    # No --french: this base must stay language-neutral so it is safe to
    # share across every generic-language build.
    run([
        PYTHON, TRILINGUAL_SCRIPT,
        "--english", ENGLISH_EXTRACT,
        "--output", GENERIC_BASE_CSV,
    ])

    if not GENERIC_BASE_CSV.exists():
        raise SystemExit("Trilingual CSV generation failed: no output file produced.")
    return GENERIC_BASE_CSV


def generate_translation_json(config) -> Path:
    """combined_<code>.txt → trilingual CSV → translation-ready JSON."""
    combined = config.combined_path(REPO_ROOT)
    if not combined.exists():
        raise SystemExit(f"Combined translation file not found: {combined}")

    TRANSLATION_DIR.mkdir(parents=True, exist_ok=True)
    base_csv = _generic_base_csv()
    lang_csv = TRANSLATION_DIR / f"{config.code}_trilingual_translation.csv"
    out_json = config.translation_json_path(REPO_ROOT)

    critical = config.critical_path(REPO_ROOT)
    # apply_combined_fr.py is language-agnostic: it only fills the translation
    # column from whatever combined file / critical file we point it at.
    apply_cmd = [
        PYTHON, APPLY_COMBINED_SCRIPT,
        "--combined", combined,
        "--csv", base_csv,
        "--output", lang_csv,
        "--extend",
        "--english", ENGLISH_EXTRACT,
        "--spanish", SPANISH_EXTRACT,
        "--rom", ENGLISH_ROM,
        "--critical", critical if critical else (REPO_ROOT / "nonexistent.txt"),
    ]
    run(apply_cmd)

    # Convert with an explicit output path so we never clobber the dated FR JSON.
    csv_to_json = _load_module(CSV_TO_JSON_SCRIPT)
    validator = csv_to_json.TranslationValidator(
        input_path=lang_csv, output_path=out_json, allow_too_long=True
    )
    stats = validator.validate_and_convert()
    print(f"✓ Translation JSON: {out_json.name} ({stats['successful']} entries)")
    return out_json


def build_rom(config, translation_json: Path) -> Path:
    out_rom = config.output_rom_path(REPO_ROOT)
    out_rom.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        PYTHON, BUILD_SCRIPT,
        "--source", ENGLISH_ROM,
        "--translations", translation_json,
        "--language", config.builder_language,
        "--allow-relocate",
        "--allow-fallback",
        # Generic (DE/IT) builds inject verbose translations into packed
        # description tables; the guard keeps every in-place write terminated
        # before the next cell so nothing fuses into / overruns a neighbour
        # (the collisions surfaced by the collision_check step). Too-long
        # entries relocate to free space instead of overwriting the next cell.
        "--collision-guard",
        # The combined file's offsets (incl. scanned phantom cells that sit in
        # padding) are the audit's cell walls; feed them in so a verbose
        # translation relocates rather than overrunning one.
        "--extra-boundaries", config.combined_path(REPO_ROOT),
        "--output", out_rom,
    ]
    if SPANISH_ROM.exists():
        cmd += ["--pointer-proof-rom", SPANISH_ROM]
    run(cmd)
    return out_rom


def _font_script_for(code: str) -> Path:
    """Return the language-specific font patch script, falling back to the FR one."""
    lang_script = REPO_ROOT / f"languages/{code}/patches/font.py"
    return lang_script if lang_script.exists() else _PATCH_FONT_FR


def _status_badges_script_for(code: str) -> Path:
    """Return the language-specific status-badge tile patch, falling back to FR."""
    lang_script = REPO_ROOT / f"languages/{code}/patches/status_badges.py"
    return lang_script if lang_script.exists() else PATCH_STATUS_BADGES_FR_SCRIPT


def _battle_prefix_script_for(code: str) -> Path:
    lang_script = REPO_ROOT / f"languages/{code}/patches/battle_prefix.py"
    return lang_script if lang_script.exists() else PATCH_BATTLE_PREFIX_FR_SCRIPT


def _battle_recall_strings_script_for(code: str) -> Path:
    lang_script = REPO_ROOT / f"languages/{code}/patches/battle_recall_strings.py"
    return lang_script if lang_script.exists() else PATCH_BATTLE_RECALL_STRINGS_FR_SCRIPT


def _battle_string_templates_script_for(code: str) -> Path:
    lang_script = REPO_ROOT / f"languages/{code}/patches/battle_string_templates.py"
    return lang_script if lang_script.exists() else PATCH_BATTLE_STRING_TEMPLATES_FR_SCRIPT


def _gendered_buffers_script_for(code: str) -> Path:
    lang_script = REPO_ROOT / f"languages/{code}/patches/gendered_buffers.py"
    return lang_script if lang_script.exists() else PATCH_GENDERED_BUFFERS_FR_SCRIPT


def _givecs_gift_item_script_for(code: str) -> Path:
    lang_script = REPO_ROOT / f"languages/{code}/patches/givecs_gift_item.py"
    return lang_script if lang_script.exists() else PATCH_GIVECS_GIFT_ITEM_FR_SCRIPT


def _lang_patch_script(step: str, code: str) -> Path | None:
    """Resolve a language-specific post-build patch script for ``step``.

    A step declared in ``lang.yaml`` maps to a
    ``languages/<code>/patches/<name>.py`` wrapper when one exists. Two
    spellings are accepted:

    * ``step`` is the bare patch name (e.g. ``ability_names``) → look for
      ``languages/<code>/patches/ability_names.py``.
    * ``step`` already carries the language suffix (e.g. ``intro_questions_it``)
      → look for ``languages/it/patches/intro_questions.py``.

    These thin wrappers take a single ``--rom`` argument and resolve their own
    Italian data sources internally, so the dispatch stays uniform. Returns
    ``None`` when no such script exists (the caller then falls back to the shared
    ``patch_*_fr.py`` branches below).
    """
    bare = REPO_ROOT / f"languages/{code}/patches/{step}.py"
    if bare.exists():
        return bare
    if step.endswith(f"_{code}"):
        trimmed = step[: -len(f"_{code}")]
        suffixed = REPO_ROOT / f"languages/{code}/patches/{trimmed}.py"
        if suffixed.exists():
            return suffixed
    return None


def apply_patches(config, out_rom: Path, translation_json: Path | None = None,
                  build_number: int = 0) -> None:
    """Run every post-build patch step declared in the language descriptor.

    ``translation_json`` is required for the ``repoint_stale`` and
    ``move_descriptions`` steps; those steps are silently skipped when it is
    not provided (e.g. when called from tests without a full build).

    ``build_number`` feeds the ``version`` step, which stamps the in-game
    NOT FOR SALE version display with ``<CODE>.2.1.<build_number>`` (e.g.
    ``IT.2.1.42`` for the Italian build).
    """
    combined = config.combined_path(REPO_ROOT)
    for step in config.patches:
        # A language-specific wrapper (languages/<code>/patches/<step>.py) takes
        # precedence over the shared French branches: it resolves its own Italian
        # data sources internally and only needs the target ROM. This is how the
        # ported Italian patches (ability_names, meteorite_dialogue, pokedex, …)
        # are dispatched — see languages/it/patches/*.py + src/i18n/fr_patch_delegate.
        lang_script = _lang_patch_script(step, config.code)
        if lang_script is not None:
            run([PYTHON, lang_script, "--rom", out_rom])
            continue

        if step == "font":
            run([PYTHON, _font_script_for(config.code), "--rom", out_rom])

        elif step == "inline":
            run([
                PYTHON, INLINE_SCRIPT,
                "--rom", out_rom,
                "--source", ENGLISH_ROM,
                "--combined", combined,
                "--reference-texts", SPANISH_EXTRACT,
                # Generic (DE/IT) builds inject verbose translations into the
                # packed description tables; the guard keeps every in-place write
                # terminated before the next cell so no string fuses into / over-
                # runs a neighbour (the collisions audited by `collision_check`).
                "--collision-guard",
            ])

        # ── Anti-freeze / anti-corruption mechanics (language-agnostic) ──────

        elif step == "repair_lz77":
            run([
                PYTHON, REPAIR_LZ77_SCRIPT,
                "--target", out_rom,
                "--english", ENGLISH_ROM,
                "--spanish", SPANISH_ROM,
            ])

        elif step == "repair_localized_lz77":
            run([
                PYTHON, REPAIR_LOCALIZED_LZ77_SCRIPT,
                "--target", out_rom,
                "--english", ENGLISH_ROM,
                "--spanish", SPANISH_ROM,
                "--require-pointer",
            ])

        elif step == "repoint_stale":
            if translation_json is None:
                print("⚠ skipping repoint_stale: translation_json not available")
            else:
                run([
                    PYTHON, REPOINT_STALE_SCRIPT,
                    "--target", out_rom,
                    "--translations", translation_json,
                    "--source", ENGLISH_ROM,
                ])

        elif step == "legendary_ritual":
            run([
                PYTHON, PATCH_RITUAL_SCRIPT,
                "--rom", out_rom,
                "--source", ENGLISH_ROM,
            ])

        elif step == "intro_questions_it":
            run([PYTHON, PATCH_INTRO_QUESTIONS_IT_SCRIPT, "--rom", out_rom])

        elif step == "trainer_class_names_it":
            # gTrainerClassNames is a fixed-width table reached by index
            # arithmetic (no pointers), so the generic pipeline skips it and
            # every class ships English. This writes the Italian names from
            # combined_it.txt in place, for the classes whose text fits the
            # 13-byte cell (overflow classes are reported and left English).
            run([
                PYTHON, PATCH_TRAINER_CLASS_NAMES_IT_SCRIPT,
                "--rom", out_rom,
                "--combined", combined,
                "--source", ENGLISH_ROM,
            ])

        elif step == "long_dialogues_it":
            # A handful of dialogues exceed the extractor's 1000-byte cap and
            # are dropped by the generic pipeline (New Game+, Battle Circus /
            # Sands / Tower rules, champion congratulation). Relocate the full
            # Italian text to free space and repoint the live pointer.
            run([
                PYTHON, PATCH_LONG_DIALOGUES_IT_SCRIPT,
                "--rom", out_rom,
                "--combined", combined,
                "--source", ENGLISH_ROM,
            ])

        elif step == "version":
            # Stamp the in-game NOT FOR SALE screen with this language's tag,
            # e.g. DE.2.1.<build> for German — so the running build advertises
            # which language it is. The version cycle comes from this language's
            # version_label descriptor (source of truth), passed explicitly so
            # patch_version_fr.py stamps exactly what lang.yaml declares.
            version_cmd = [
                PYTHON, PATCH_VERSION_SCRIPT,
                "--rom", out_rom,
                "--lang-code", config.code,
                "--build-number", str(build_number),
            ]
            if config.version_label:
                version_cmd += ["--version-label", config.version_label]
            run(version_cmd)

        # ── Text patches parameterised from the language descriptor ──────────

        elif step == "status_abbrevs":
            run([
                PYTHON, PATCH_STATUS_ABBREVS_SCRIPT,
                "--rom", out_rom,
                "--lang-code", config.code,
            ])

        elif step == "status_badges":
            # In-battle status badges are LZ77 tile graphics, so each language
            # ships its own glyphs (patch_status_badges_<code>.py). The FR
            # script is the fallback for languages that reuse the same badges.
            run([
                PYTHON, _status_badges_script_for(config.code),
                "--rom", out_rom,
            ])

        elif step == "tm_item_descriptions":
            cmd = [
                PYTHON, PATCH_TM_ITEM_DESC_SCRIPT,
                "--rom", out_rom,
                "--combined", combined,
            ]
            if SPANISH_ROM.exists():
                cmd += ["--reference-rom", SPANISH_ROM]
            run(cmd)

        elif step == "move_descriptions":
            if translation_json is None:
                print("⚠ skipping move_descriptions: translation_json not available")
            else:
                run([
                    PYTHON, PATCH_MOVE_DESC_SCRIPT,
                    "--rom", out_rom,
                    "--source", ENGLISH_ROM,
                    "--translations", translation_json,
                ])

        elif step == "type_icons":
            # Redraw the move-type badges (graphic tiles, not text) in this
            # language via languages/<code>/patches/type_icons.py. Each language ships
            # its own script because the badge names are baked pixels drawn with a
            # per-language glyph set (German adds K/D/W/Z, French adds none).
            script = REPO_ROOT / f"languages/{config.code}/patches/type_icons.py"
            if script.exists():
                run([PYTHON, script, "--rom", out_rom])
            else:
                print(f"⚠ skipping type_icons: {script.name} not found")

        elif step == "hp_labels":
            # Redraw the HP-label graphics (party menu + summary bar + summary
            # grey stat label — all 4bpp tiles inside LZ77 blocks, not text) with
            # this language's abbreviation via languages/<code>/patches/hp_labels.py.
            # Each language ships its own script because the label is baked pixels
            # (German « KP », French « PV »).
            script = REPO_ROOT / f"languages/{config.code}/patches/hp_labels.py"
            if script.exists():
                run([PYTHON, script, "--rom", out_rom])
            else:
                print(f"⚠ skipping hp_labels: {script.name} not found")

        elif step == "battle_prefix":
            run([PYTHON, _battle_prefix_script_for(config.code), "--rom", out_rom])

        elif step == "battle_recall_strings":
            run([PYTHON, _battle_recall_strings_script_for(config.code), "--rom", out_rom])

        elif step == "battle_string_templates":
            run([
                PYTHON, _battle_string_templates_script_for(config.code),
                "--rom", out_rom,
                "--source", ENGLISH_ROM,
            ])

        elif step == "gendered_buffers":
            run([PYTHON, _gendered_buffers_script_for(config.code), "--rom", out_rom])

        elif step == "givecs_gift_item":
            run([
                PYTHON, _givecs_gift_item_script_for(config.code),
                "--rom", out_rom,
                "--source", ENGLISH_ROM,
            ])

        elif step == "time_format":
            # Inline ASM/text patch for the in-game clock/date displays.
            # Only German has a dedicated script today; other generic
            # languages skip it until one is written for them.
            script = REPO_ROOT / f"languages/{config.code}/patches/time_format.py"
            if script.exists():
                run([PYTHON, script, "--rom", out_rom])
            else:
                print(f"⚠ skipping time_format: no {script.name}")

        elif step == "trainer_card_date":
            # Free-space builder + veneer redirect for the Trainer Card date.
            script = REPO_ROOT / f"languages/{config.code}/patches/trainer_card_date.py"
            if script.exists():
                run([PYTHON, script, "--rom", out_rom])
            else:
                print(f"⚠ skipping trainer_card_date: no {script.name}")

        elif step == "dexnav_headers":
            # Redraw the 4 DexNav column-header graphics (SEARCH LEVEL / METHOD /
            # HIDDEN ABILITY / HELD ITEMS — baked 4bpp tiles inside a custom
            # Unbound LZ77 block, not text) with this language's labels via
            # languages/<code>/patches/dexnav_headers.py. Each language ships its own
            # script because the labels are baked pixels drawn with a per-language
            # glyph set (German adds F/G/K, French adds none).
            script = REPO_ROOT / f"languages/{config.code}/patches/dexnav_headers.py"
            if script.exists():
                run([PYTHON, script, "--rom", out_rom])
            else:
                print(f"⚠ skipping dexnav_headers: {script.name} not found")

        # ── Pokédex patches, resolved per-language ─────────────────────────────
        # Each carries baked official localisation content (category words,
        # metric-system labels, rewrap data), so every language ships its own
        # languages/<code>/patches/<step>.py; a missing script just skips the step
        # (e.g. a future language that hasn't authored this data yet).

        elif step == "pokedex_categories":
            script = REPO_ROOT / f"languages/{config.code}/patches/pokedex_categories.py"
            if script.exists():
                run([PYTHON, script, "--rom", out_rom])
            else:
                print(f"⚠ skipping pokedex_categories: {script.name} not found")

        elif step == "pokedex_category_order":
            script = REPO_ROOT / f"languages/{config.code}/patches/pokedex_category_order.py"
            if script.exists():
                run([PYTHON, script, "--rom", out_rom])
            else:
                print(f"⚠ skipping pokedex_category_order: {script.name} not found")

        elif step == "pokedex_metrics":
            script = REPO_ROOT / f"languages/{config.code}/patches/pokedex_metrics.py"
            if script.exists():
                run([PYTHON, script, "--rom", out_rom])
            else:
                print(f"⚠ skipping pokedex_metrics: {script.name} not found")

        elif step == "pokedex_rewrap":
            if translation_json is None:
                print("⚠ skipping pokedex_rewrap: translation_json not available")
            else:
                script = REPO_ROOT / f"languages/{config.code}/patches/pokedex.py"
                if not script.exists():
                    print(f"⚠ skipping pokedex_rewrap: {script.name} not found")
                else:
                    cmd = [
                        PYTHON, script,
                        "--rom", out_rom,
                        "--source", ENGLISH_ROM,
                        "--translations", translation_json,
                    ]
                    if SPANISH_ROM.exists():
                        cmd += ["--reference-rom", SPANISH_ROM]
                    run(cmd)

        # ── German-only fixed-table name/description patches ──────────────────
        # These carry baked official German localisation content (not read
        # from combined_de.txt), so — unlike the steps above — they are not
        # parameterised per-language; they simply don't apply to other
        # generic-build languages (e.g. Italian) until a patch_<name>_it.py
        # is written and wired in separately.

        elif step == "item_names":
            run([PYTHON, PATCH_ITEM_NAMES_DE_SCRIPT, "--rom", out_rom])

        elif step == "nature_names":
            cmd = [PYTHON, PATCH_NATURE_NAMES_DE_SCRIPT, "--rom", out_rom]
            if SPANISH_ROM.exists():
                cmd += ["--reference-rom", SPANISH_ROM]
            run(cmd)

        elif step == "cfru_type_names":
            run([PYTHON, PATCH_CFRU_TYPE_NAMES_DE_SCRIPT, "--rom", out_rom])

        elif step == "summary_labels":
            run([
                PYTHON, PATCH_SUMMARY_LABELS_DE_SCRIPT,
                "--rom", out_rom,
                "--source", ENGLISH_ROM,
            ])

        elif step == "options_footer":
            run([PYTHON, PATCH_OPTIONS_FOOTER_DE_SCRIPT, "--rom", out_rom])

        elif step == "shop":
            cmd = [PYTHON, PATCH_SHOP_DE_SCRIPT, "--rom", out_rom]
            if SPANISH_ROM.exists():
                cmd += ["--reference-rom", SPANISH_ROM]
            run(cmd)

        elif step == "pc_messages":
            run([PYTHON, PATCH_PC_MESSAGES_DE_SCRIPT, "--rom", out_rom])

        elif step == "collision_check":
            # Report-only: trace live pointers in the finished ROM and flag any
            # cell whose string is not terminated before the next occupied
            # offset (fusion / freeze risk). Never fails the build so a
            # pre-existing collision is surfaced, not hidden — the fix is to
            # shorten/relocate the offending translation in combined_<code>.txt.
            run([
                PYTHON, AUDIT_COLLISIONS_SCRIPT,
                "--combined", combined,
                "--rom", out_rom,
                "--english", ENGLISH_ROM,
            ])

        else:
            print(f"⚠ skipping unknown/unsupported generic patch step: {step!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("language", help="Language code (e.g. it, de)")
    parser.add_argument("--build-number", type=int, default=0)
    args = parser.parse_args()

    try:
        registry = load_registry()
        config = registry.get(args.language)
    except RegistryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if config.is_dedicated:
        print(
            f"{config.name} uses its dedicated, byte-perfect recipe.\n"
            f"  Build it with:  make build-{config.code}"
        )
        return 0

    print("=" * 70)
    print(f"🌍 GENERIC MULTI-LANGUAGE BUILD — {config.name} ({config.code})")
    print("=" * 70)

    check_translation_integrity(config.code)
    ensure_extractions()
    translation_json = generate_translation_json(config)
    out_rom = build_rom(config, translation_json)
    apply_patches(config, out_rom, translation_json, args.build_number)

    print("\n" + "=" * 70)
    print(f"✓ {config.name} ROM built: {out_rom.relative_to(REPO_ROOT)}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
