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
_PATCH_FONT_FR = REPO_ROOT / "scripts/patch_font_fr.py"
INLINE_SCRIPT = REPO_ROOT / "scripts/apply_inline_overrides_fr.py"

# Anti-freeze / anti-corruption patches (language-agnostic mechanics).
REPAIR_LZ77_SCRIPT = REPO_ROOT / "scripts/repair_stable_lz77_blocks.py"
REPAIR_LOCALIZED_LZ77_SCRIPT = REPO_ROOT / "scripts/repair_localized_lz77_blocks.py"
REPOINT_STALE_SCRIPT = REPO_ROOT / "scripts/repoint_stale_text_pointers.py"
PATCH_RITUAL_SCRIPT = REPO_ROOT / "scripts/patch_legendary_ritual_fr.py"
PATCH_VERSION_SCRIPT = REPO_ROOT / "scripts/patch_version_fr.py"
PATCH_INTRO_QUESTIONS_IT_SCRIPT = REPO_ROOT / "scripts/patch_intro_questions_it.py"

# Text patches that can be parameterised with the language's combined file.
PATCH_STATUS_ABBREVS_SCRIPT = REPO_ROOT / "scripts/patch_status_abbrevs_fr.py"
PATCH_TM_ITEM_DESC_SCRIPT = REPO_ROOT / "scripts/patch_tm_item_descriptions_fr.py"
PATCH_MOVE_DESC_SCRIPT = REPO_ROOT / "scripts/patch_move_descriptions_fr.py"

# Graphic (LZ77 tile) patches whose glyphs differ per language, so each ships a
# dedicated per-language script (patch_status_badges_<code>.py). Unlike the text
# status_abbrevs table, the in-battle status badges are drawn as tiles and must
# be redrawn with the target language's letter shapes.
PATCH_STATUS_BADGES_FR_SCRIPT = REPO_ROOT / "scripts/patch_status_badges_fr.py"

# Battle-text / control-code-timing / positional-gender-buffer patches. Each
# ships a dedicated per-language script (patch_<name>_<code>.py) because the
# phrasing and byte-budget constraints are language-structure specific; the FR
# script is the fallback for languages that have not ported it yet.
PATCH_BATTLE_PREFIX_FR_SCRIPT = REPO_ROOT / "scripts/patch_battle_prefix_fr.py"
PATCH_BATTLE_RECALL_STRINGS_FR_SCRIPT = REPO_ROOT / "scripts/patch_battle_recall_strings_fr.py"
PATCH_BATTLE_STRING_TEMPLATES_FR_SCRIPT = REPO_ROOT / "scripts/patch_battle_string_templates_fr.py"
PATCH_GENDERED_BUFFERS_FR_SCRIPT = REPO_ROOT / "scripts/patch_gendered_buffers_fr.py"
PATCH_GIVECS_GIFT_ITEM_FR_SCRIPT = REPO_ROOT / "scripts/patch_givecs_gift_item_fr.py"

# German-only post-build patches: fixed-width name/description tables whose
# translated content is baked into the script (official German localisation),
# not read from combined_de.txt — so, unlike the steps above, these have no
# generic "run the FR script with --combined" delegation and are wired
# directly to their scripts/patch_<name>_de.py implementation.
PATCH_ITEM_NAMES_DE_SCRIPT = REPO_ROOT / "scripts/patch_item_names_de.py"
PATCH_NATURE_NAMES_DE_SCRIPT = REPO_ROOT / "scripts/patch_nature_names_de.py"
PATCH_CFRU_TYPE_NAMES_DE_SCRIPT = REPO_ROOT / "scripts/patch_cfru_type_names_de.py"
PATCH_POKEDEX_DE_SCRIPT = REPO_ROOT / "scripts/patch_pokedex_de.py"
PATCH_POKEDEX_CATEGORIES_DE_SCRIPT = REPO_ROOT / "scripts/patch_pokedex_categories_de.py"
PATCH_POKEDEX_CATEGORY_ORDER_DE_SCRIPT = REPO_ROOT / "scripts/patch_pokedex_category_order_de.py"
PATCH_POKEDEX_METRICS_DE_SCRIPT = REPO_ROOT / "scripts/patch_pokedex_metrics_de.py"
PATCH_SUMMARY_LABELS_DE_SCRIPT = REPO_ROOT / "scripts/patch_summary_labels_de.py"
PATCH_OPTIONS_FOOTER_DE_SCRIPT = REPO_ROOT / "scripts/patch_options_footer_de.py"
PATCH_SHOP_DE_SCRIPT = REPO_ROOT / "scripts/patch_shop_de.py"
PATCH_PC_MESSAGES_DE_SCRIPT = REPO_ROOT / "scripts/patch_pc_messages_de.py"

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


def run(cmd: list, *, cwd: Path = REPO_ROOT) -> None:
    printable = " ".join(str(part) for part in cmd)
    print(f"\n$ {printable}")
    subprocess.run([str(part) for part in cmd], cwd=str(cwd), check=True)


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


def _latest_base_csv() -> Path:
    """Return the most recent trilingual CSV, generating it if necessary."""
    candidates = sorted(
        TRANSLATION_DIR.glob("*_trilingual_translation.csv"),
        key=lambda p: p.stat().st_mtime,
    )
    if candidates:
        return candidates[-1]

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
    run([PYTHON, TRILINGUAL_SCRIPT, "--english", ENGLISH_EXTRACT])

    candidates = sorted(
        TRANSLATION_DIR.glob("*_trilingual_translation.csv"),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise SystemExit("Trilingual CSV generation failed: no output file produced.")
    return candidates[-1]


def generate_translation_json(config) -> Path:
    """combined_<code>.txt → trilingual CSV → translation-ready JSON."""
    combined = config.combined_path(REPO_ROOT)
    if not combined.exists():
        raise SystemExit(f"Combined translation file not found: {combined}")

    TRANSLATION_DIR.mkdir(parents=True, exist_ok=True)
    base_csv = _latest_base_csv()
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
    lang_script = REPO_ROOT / f"scripts/patch_font_{code}.py"
    return lang_script if lang_script.exists() else _PATCH_FONT_FR


def _status_badges_script_for(code: str) -> Path:
    """Return the language-specific status-badge tile patch, falling back to FR."""
    lang_script = REPO_ROOT / f"scripts/patch_status_badges_{code}.py"
    return lang_script if lang_script.exists() else PATCH_STATUS_BADGES_FR_SCRIPT


def _battle_prefix_script_for(code: str) -> Path:
    lang_script = REPO_ROOT / f"scripts/patch_battle_prefix_{code}.py"
    return lang_script if lang_script.exists() else PATCH_BATTLE_PREFIX_FR_SCRIPT


def _battle_recall_strings_script_for(code: str) -> Path:
    lang_script = REPO_ROOT / f"scripts/patch_battle_recall_strings_{code}.py"
    return lang_script if lang_script.exists() else PATCH_BATTLE_RECALL_STRINGS_FR_SCRIPT


def _battle_string_templates_script_for(code: str) -> Path:
    lang_script = REPO_ROOT / f"scripts/patch_battle_string_templates_{code}.py"
    return lang_script if lang_script.exists() else PATCH_BATTLE_STRING_TEMPLATES_FR_SCRIPT


def _gendered_buffers_script_for(code: str) -> Path:
    lang_script = REPO_ROOT / f"scripts/patch_gendered_buffers_{code}.py"
    return lang_script if lang_script.exists() else PATCH_GENDERED_BUFFERS_FR_SCRIPT


def _givecs_gift_item_script_for(code: str) -> Path:
    lang_script = REPO_ROOT / f"scripts/patch_givecs_gift_item_{code}.py"
    return lang_script if lang_script.exists() else PATCH_GIVECS_GIFT_ITEM_FR_SCRIPT


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
            # language via scripts/patch_type_icons_<code>.py. Each language ships
            # its own script because the badge names are baked pixels drawn with a
            # per-language glyph set (German adds K/D/W/Z, French adds none).
            script = REPO_ROOT / f"scripts/patch_type_icons_{config.code}.py"
            if script.exists():
                run([PYTHON, script, "--rom", out_rom])
            else:
                print(f"⚠ skipping type_icons: {script.name} not found")

        elif step == "hp_labels":
            # Redraw the HP-label graphics (party menu + summary bar + summary
            # grey stat label — all 4bpp tiles inside LZ77 blocks, not text) with
            # this language's abbreviation via scripts/patch_hp_labels_<code>.py.
            # Each language ships its own script because the label is baked pixels
            # (German « KP », French « PV »).
            script = REPO_ROOT / f"scripts/patch_hp_labels_{config.code}.py"
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

        elif step == "dexnav_headers":
            # Redraw the 4 DexNav column-header graphics (SEARCH LEVEL / METHOD /
            # HIDDEN ABILITY / HELD ITEMS — baked 4bpp tiles inside a custom
            # Unbound LZ77 block, not text) with this language's labels via
            # scripts/patch_dexnav_headers_<code>.py. Each language ships its own
            # script because the labels are baked pixels drawn with a per-language
            # glyph set (German adds F/G/K, French adds none).
            script = REPO_ROOT / f"scripts/patch_dexnav_headers_{config.code}.py"
            if script.exists():
                run([PYTHON, script, "--rom", out_rom])
            else:
                print(f"⚠ skipping dexnav_headers: {script.name} not found")

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

        elif step == "pokedex_categories":
            run([PYTHON, PATCH_POKEDEX_CATEGORIES_DE_SCRIPT, "--rom", out_rom])

        elif step == "pokedex_category_order":
            run([PYTHON, PATCH_POKEDEX_CATEGORY_ORDER_DE_SCRIPT, "--rom", out_rom])

        elif step == "pokedex_metrics":
            run([PYTHON, PATCH_POKEDEX_METRICS_DE_SCRIPT, "--rom", out_rom])

        elif step == "pokedex_rewrap":
            if translation_json is None:
                print("⚠ skipping pokedex_rewrap: translation_json not available")
            else:
                cmd = [
                    PYTHON, PATCH_POKEDEX_DE_SCRIPT,
                    "--rom", out_rom,
                    "--source", ENGLISH_ROM,
                    "--translations", translation_json,
                ]
                if SPANISH_ROM.exists():
                    cmd += ["--reference-rom", SPANISH_ROM]
                run(cmd)

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
